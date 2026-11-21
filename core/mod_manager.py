import os
import sys
import threading
from typing import Dict

# Ensure core directory is on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from adb_bridge import ADBBridge
from mod_cache import CacheMixin
from dating_audio import DatingAudioMixin
from mod_duplicates import DuplicatesMixin
from mod_installer import InstallerMixin
from mod_queue import QueueMixin
from mod_scanner import ScannerMixin
from prepare_gate import PrepareGate
from mod_spine_tools import SpineToolsMixin


class ModManager(ScannerMixin, InstallerMixin, SpineToolsMixin, CacheMixin, QueueMixin, DuplicatesMixin, DatingAudioMixin):
    """Facade over the mod pipeline; behaviour lives in the mixins, state is set up here."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.work_dir = os.path.join(self.workspace_dir, "work")
        self.cache_dir = os.path.join(self.work_dir, "cache")
        self.originals_dir = os.path.join(self.work_dir, "originals")
        self.repacked_dir = os.path.join(self.work_dir, "repacked")
        self.multi_cache_dir = os.path.join(self.work_dir, "multi_preview_cache")
        self.thumbs_dir = os.path.join(self.work_dir, "thumbs")
        self.audio_dir = os.path.join(self.work_dir, "audio")  # dating-scene sounds; survives "clear cache"
        self.adb = ADBBridge()
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.originals_dir, exist_ok=True)
        os.makedirs(self.repacked_dir, exist_ok=True)
        os.makedirs(self.multi_cache_dir, exist_ok=True)

        self.catalog_cache = {}
        self.catalog_lock = threading.Lock()
        # Concurrency of the two stages of preparing a mod; `work_limit` is replaced by the web layer (Turbo Mode setting).
        self.work_limit = lambda: 1
        self.download_gate = PrepareGate(lambda: 3)
        self.work_gate = PrepareGate(lambda: self.work_limit())
        self.cached_indexes = {}
        self.index_lock = threading.Lock()  # one caller builds the asset index (a 70 MB catalog download the first time), the others wait for it
        self._bundle_locks: Dict[str, threading.Lock] = {}  # per original bundle: two mods of one bundle download it once
        self._bundle_locks_guard = threading.Lock()

        self.scan_cache = {}
        self.scan_cache_lock = threading.Lock()
