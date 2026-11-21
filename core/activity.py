"""What the program is doing right now, kept on the server so every page (and a page opened later, or in another browser) sees the same.

A *task* is one operation (a download, a repack, an install...). Log lines belong to the task that wrote them, give it its newest
detail line and progress, and count its errors. `status()` is the single light the interface shows:
blue = standby, green = running, orange = running but errors were logged, red = the last operation failed and nothing runs.
"""
import collections
import itertools
import re
import threading
import time
from typing import Callable, Dict, List, Optional

KEEP_LOGS = 3000
KEEP_FINISHED = 60
BROWSER_SILENCE = 90  # seconds: work reported by a page that stops reporting (the tab was closed) is ended as cancelled
PUBLISH_EVERY = 0.15  # seconds: log bursts reach the pages in at most this many updates per second

_local = threading.local()
_SIZE = re.compile(r"([\d.]+)\s*(KB|MB|GB)?\s*/\s*([\d.]+)\s*(KB|MB|GB)", re.I)
_UNIT = {"KB": 1, "MB": 1024, "GB": 1024 * 1024, None: None}


def _fraction(message: str) -> Optional[float]:
    """The share done when a line says "Downloading... 433792.00 KB / 436549.66 KB" (a unit missing on the left is the right one's)."""
    found = _SIZE.search(message)
    if not found:
        return None
    done, left_unit, total, right_unit = found.groups()
    right = _UNIT[right_unit.upper()]
    left = _UNIT[left_unit.upper()] if left_unit else right
    try:
        return min(1.0, float(done) * left / (float(total) * right)) if float(total) else None
    except ValueError:
        return None


class Hub:
    def __init__(self):
        self.lock = threading.RLock()
        self.tasks: Dict[int, dict] = {}
        self.logs = collections.deque(maxlen=KEEP_LOGS)
        self._ids = itertools.count(1)
        self._seq = itertools.count(1)
        self.acknowledged = 0  # failures of tasks up to this id no longer turn the light red
        self.on_change: Optional[Callable[[], None]] = None
        self.emit: Callable[..., None] = self.log  # the web layer swaps in a function that also prints and broadcasts
        self._last_publish = 0.0
        self._timer: Optional[threading.Timer] = None

    # ---- tasks -------------------------------------------------------------------------------------------------------
    def start(self, title: str, kind: str = "work") -> dict:
        with self.lock:
            task = {"id": next(self._ids), "title": title, "kind": kind, "state": "running", "detail": "", "progress": None,
                    "errors": 0, "error": "", "started": time.time(), "ended": None, "updated": time.time()}
            self.tasks[task["id"]] = task
            self._prune()
        if kind == "browser":
            self._watch()
        self._publish(True)
        return task

    def _watch(self) -> None:
        timer = threading.Timer(BROWSER_SILENCE / 3, self._sweep)
        timer.daemon = True
        timer.start()

    def _sweep(self) -> None:
        """Ends browser-run tasks whose page went silent, and keeps watching while any still runs."""
        now, again = time.time(), False
        for task in list(self.tasks.values()):
            if task["kind"] == "browser" and task["state"] == "running":
                if now - task["updated"] > BROWSER_SILENCE:
                    self.finish(task["id"], "cancelled", "The page that was doing this was closed")
                else:
                    again = True
        if again:
            self._watch()

    def finish(self, task_id: int, state: str = "done", error: str = "") -> None:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or task["state"] != "running":
                return
            task.update(state=state, error=error, ended=time.time(), updated=time.time())
            if state == "done":
                task["progress"] = 1.0
        self._publish(True)

    def _prune(self) -> None:
        finished = [t for t in self.tasks.values() if t["state"] != "running"]
        for task in finished[:-KEEP_FINISHED]:
            del self.tasks[task["id"]]

    def current(self) -> Optional[int]:
        """The task a log line without an explicit one belongs to: the one this thread opened, else the newest running one."""
        stack = getattr(_local, "stack", None)
        if stack:
            return stack[-1]
        with self.lock:
            running = [t["id"] for t in self.tasks.values() if t["state"] == "running"]
        return running[-1] if running else None

    # ---- log ---------------------------------------------------------------------------------------------------------
    def log(self, message: str, level: str = "info", progress: Optional[float] = None, task: Optional[int] = None) -> dict:
        task_id = task if task is not None else self.current()
        with self.lock:
            entry = {"seq": next(self._seq), "message": message, "level": level, "progress": progress, "at": int(time.time() * 1000), "task": task_id}
            self.logs.append(entry)
            owner = self.tasks.get(task_id) if task_id is not None else None
            if owner and owner["state"] == "running":
                if level == "error":
                    owner["errors"] += 1
                if not message.startswith(("SUCCESS", "FAILED")):
                    owner["detail"] = message
                share = progress / 100 if progress is not None else _fraction(message)
                if share is not None:
                    owner["progress"] = max(0.0, min(1.0, share))
                owner["updated"] = time.time()
        self._publish(False)
        return entry

    # ---- state for the pages -----------------------------------------------------------------------------------------
    def status(self) -> dict:
        with self.lock:
            running = [t for t in self.tasks.values() if t["state"] == "running"]
            finished = [t for t in self.tasks.values() if t["state"] != "running"]
            if running:
                broken = any(t["errors"] for t in running)
                state = "warning" if broken else "running"
                latest = running[-1]
                text = f"{latest['title']}" + (f" - {latest['detail']}" if latest["detail"] else "")
                if len(running) > 1:
                    text += f"  (+{len(running) - 1} more)"
                return {"state": state, "label": "Errors, running" if broken else "Running", "text": text, "running": len(running)}
            last = max(finished, key=lambda t: t["ended"] or 0, default=None)
            if last and last["state"] == "error" and last["id"] > self.acknowledged:
                return {"state": "error", "label": "Critical Failure", "text": f"{last['title']} failed: {last['error'] or 'see the console'}", "running": 0}
            return {"state": "idle", "label": "Standby", "text": "Nothing is running.", "running": 0}

    def acknowledge(self) -> None:
        with self.lock:
            self.acknowledged = max(self.tasks, default=0)
        self._publish(True)

    def snapshot(self) -> dict:
        with self.lock:
            tasks = sorted(self.tasks.values(), key=lambda t: (t["state"] != "running", -(t["ended"] or t["started"])))
            return {"tasks": [dict(t) for t in tasks], "status": self.status(), "now": time.time()}

    def history(self, limit: int = 600) -> List[dict]:
        with self.lock:
            return list(self.logs)[-limit:]

    # ---- telling the pages ---------------------------------------------------------------------------------------------
    def _publish(self, force: bool) -> None:
        if not self.on_change:
            return
        with self.lock:
            wait = PUBLISH_EVERY - (time.monotonic() - self._last_publish)
            if not force and wait > 0:
                if self._timer is None:  # the newest state still goes out once the pause is over
                    self._timer = threading.Timer(wait, self._flush)
                    self._timer.daemon = True
                    self._timer.start()
                return
            self._last_publish = time.monotonic()
        self.on_change()

    def _flush(self) -> None:
        with self.lock:
            self._timer = None
            self._last_publish = time.monotonic()
        if self.on_change:
            self.on_change()


hub = Hub()


class Scope:
    """`with task("Installing X") as t:` - everything logged through `t.log` (or by this thread) belongs to the task; leaving the block
    ends it: done, or failed when an exception leaves it (`t.fail(...)` marks a failure that was returned rather than raised)."""

    def __init__(self, title: str, kind: str = "work", hub: Hub = hub):
        self.hub, self.title, self.kind = hub, title, kind
        self.state, self.error = "done", ""
        self.task: dict = {}

    @property
    def id(self) -> int:
        return self.task["id"]

    def __enter__(self) -> "Scope":
        self.task = self.hub.start(self.title, self.kind)
        _local.__dict__.setdefault("stack", []).append(self.id)
        return self

    def log(self, message: str, level: str = "info", progress: Optional[float] = None) -> None:
        self.hub.emit(message, level, progress, self.id)

    def fail(self, error: str) -> None:
        self.state, self.error = "error", str(error)

    def cancel(self) -> None:
        self.state = "cancelled"

    def __exit__(self, exc_type, exc, tb) -> None:
        stack = getattr(_local, "stack", [])
        if self.id in stack:
            stack.remove(self.id)
        if exc is not None:
            detail = getattr(exc, "detail", None) or str(exc) or exc_type.__name__
            self.hub.emit(f"{self.title} failed: {detail}", "error", None, self.id)
            self.hub.finish(self.id, "error", str(detail))
        else:
            self.hub.finish(self.id, self.state, self.error)


def task(title: str, kind: str = "work") -> Scope:
    return Scope(title, kind)
