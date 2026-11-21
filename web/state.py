"""Shared application state: paths, the database, the mod manager, config/queue access, and log streaming."""
import asyncio
import ntpath
import os
import sys
from typing import List, Optional

from fastapi import WebSocket

CORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from paths import DATA_DIR as BASE_DIR, MODS_DIR, STATIC_DIR  # BASE_DIR: where settings, database and work/ are kept

# Legacy JSON state files: imported into the database once, then left untouched.
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
QUEUE_STATE_PATH = os.path.join(BASE_DIR, "queue_state.json")
CHARACTERS_PATH = os.path.join(BASE_DIR, "characters.json")
DB_PATH = os.environ.get("BD2_STATE_DB") or os.path.join(BASE_DIR, "state.db")

DEFAULT_PORT = 8082
CURRENT_PORT = DEFAULT_PORT  # set by app.run_server
server = None  # the uvicorn server, set by app.run_server (POST /api/quit stops it)

from activity import hub, task as track
from characters import CharacterManager
from db import Database, import_legacy_json
from mod_manager import ModManager

manager = ModManager(BASE_DIR)
db = Database(DB_PATH)
if DB_PATH != ":memory:":
    imported = import_legacy_json(db, CONFIG_PATH, QUEUE_STATE_PATH, CHARACTERS_PATH)
    if imported:
        print(f"[State] Imported {', '.join(imported)} from legacy JSON into {DB_PATH}")
character_manager = CharacterManager(BASE_DIR, db)
import dating_audio  # noqa: E402
dating_audio.set_scene_links(character_manager.characters)
# Turbo Mode (a setting) lets several mods repack at once; by default one works at a time.
manager.work_limit = lambda: 3 if (db.get_config().get("settings") or {}).get("turbo_mode") else 1

def first_launch_setup():
    """On the very first start only: create the Mods folder next to the program and make it the first folder tab, so the user knows where
    to put mods. Later starts neither look for nor create it (the user may rename, move or remove it)."""
    if DB_PATH == ":memory:" or db.get_meta("first_launch_done"):
        return
    if not db.has_config():  # an existing installation keeps its settings
        os.makedirs(MODS_DIR, exist_ok=True)
        db.save_config({"mods_dir": MODS_DIR, "folder_tabs": [{"id": "tab_default", "name": "Mods", "path": MODS_DIR}]})
    db.set_meta("first_launch_done", "1")


first_launch_setup()


def configured_quality() -> str:
    """The texture quality chosen in Settings (what Tools and the sound/portrait downloads use too), HD when none was chosen."""
    return str(load_config().get("quality") or "HD")


def load_config():
    """The stored settings with defaults filled in. There is no default folder: with no folder tabs the manager has nothing to work on
    (the first start creates one, see first_launch_setup; the user may remove it)."""
    cfg = db.get_config()
    if "quality" not in cfg:
        cfg["quality"] = "HD"
    cfg.setdefault("folder_tabs", [])
    tabs = cfg["folder_tabs"]
    if tabs and cfg.get("active_tab_id") not in {t.get("id") for t in tabs}:
        cfg["active_tab_id"] = tabs[0]["id"]
    elif not tabs:
        cfg["active_tab_id"] = ""
    if "installed_mods" not in cfg:
        cfg["installed_mods"] = []
    if "templates" not in cfg:
        cfg["templates"] = {}
    if "settings" not in cfg:
        cfg["settings"] = {
            "expand_console_default": False,
            "auto_expand_on_install": False,
            "auto_mark_installed": True,
            "show_legend": True
        }
    return cfg

def save_config(cfg):
    db.save_config(cfg)

def load_queue_state() -> List[dict]:
    items = db.load_queue()

    # Cached bundles may be copied between Windows and Linux workspaces.
    items = [item for item in items if isinstance(item, dict)]
    for item in items:
        prep = item.get("prepared_data")
        for container in (item, prep) if isinstance(prep, dict) else (item,):
            rp = container.get("repacked_path")
            if isinstance(rp, str) and rp and not os.path.exists(rp):
                normalized = rp.replace("\\", "/")
                folder_candidate = ntpath.basename(normalized)
                if folder_candidate == "__data":
                    folder_candidate = ntpath.basename(ntpath.dirname(normalized))
                local_candidate = os.path.join(manager.repacked_dir, folder_candidate, "__data")
                if os.path.isfile(local_candidate):
                    container["repacked_path"] = local_candidate

    return items

def save_queue_state(queue_items: list) -> bool:
    try:
        db.save_queue(queue_items)
        return True
    except Exception as e:
        print(f"[Queue State] Failed to save queue: {e}")
        return False

# WebSocket manager for live log streaming
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # A page that opens (or reopens, or reconnects) learns what has happened and what is running right now.
        await websocket.send_json({"type": "history", "logs": hub.history()})
        await websocket.send_json({"type": "activity", **hub.snapshot()})
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()
loop = None  # the server's event loop, set at startup: background threads hand their messages to it


def _send(payload: dict):
    """Broadcast from any thread."""
    target = loop
    if target is not None and target.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), target)
        return
    try:  # before the server runs (tests, start-up): nothing is connected anyway
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(ws_manager.broadcast(payload))
        new_loop.close()
    except Exception:
        pass


def emit_log(message: str, level: str = "info", progress: Optional[int] = None, task: Optional[int] = None):
    """Log line from any thread: printed (manager.log), kept for pages that open later, and sent to the open ones."""
    entry = hub.log(message, level, progress, task)
    _send({"type": "log", **entry})
    print(f"[{level.upper()}] {message}")


def tracked(title: str, kind: str = "work"):
    """Decorator for a plain (sync) endpoint: its whole run is one activity task."""
    import functools

    def wrap(fn):
        @functools.wraps(fn)
        def run(*args, **kwargs):
            with track(title, kind):
                return fn(*args, **kwargs)
        return run
    return wrap


hub.emit = emit_log
hub.on_change = lambda: _send({"type": "activity", **hub.snapshot()})
