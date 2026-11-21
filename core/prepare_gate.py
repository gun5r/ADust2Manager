"""Limits how many mods may be in one stage of preparation at once (downloading, or repacking with ASTC)."""
import threading
from contextlib import contextmanager
from typing import Callable, Optional


class Cancelled(Exception):
    """The job was cancelled while it waited for a slot."""


class PrepareGate:
    def __init__(self, limit: Callable[[], int]):
        # `limit` is read on every wake-up, so changing a setting (Turbo Mode) applies to jobs that are already waiting.
        self._limit = limit
        self._active = 0
        self._cond = threading.Condition()

    @contextmanager
    def slot(self, is_cancelled: Optional[Callable[[], bool]] = None, on_wait: Optional[Callable[[], None]] = None):
        waited = False
        with self._cond:
            while self._active >= max(1, int(self._limit())):
                if is_cancelled and is_cancelled():
                    raise Cancelled()
                if not waited and on_wait:
                    waited = True
                    on_wait()
                self._cond.wait(0.5)
            self._active += 1
        try:
            yield
        finally:
            with self._cond:
                self._active -= 1
                self._cond.notify_all()
