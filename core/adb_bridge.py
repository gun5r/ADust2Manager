import socket
import subprocess
import shutil
import time
import re
import os
import shlex
import uuid
from typing import List, Dict, Optional, Tuple

from adb_install import local_adb
from game_info import PACKAGE_NAME
REMOTE_CACHE_DIR = f"/sdcard/Android/data/{PACKAGE_NAME}/files/UnityCache/Shared"

class ADBBridge:
    def __init__(self, adb_path: Optional[str] = None):
        self.adb_bin = adb_path or self._discover_adb()
        self._game_installed: Dict[str, Tuple[float, bool]] = {}
        self.started_server = False  # True when this program had to start the adb server

    @staticmethod
    def _discover_adb() -> str:
        which = shutil.which("adb")
        if which:
            return which
        downloaded = local_adb()
        if downloaded:
            return downloaded
        if os.name == "nt":
            local_app = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            prog_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
            candidates = [
                os.path.join(local_app, "Android", "Sdk", "platform-tools", "adb.exe"),
                os.path.join(prog_files, "Nox", "bin", "nox_adb.exe"),
                os.path.join(prog_x86, "Nox", "bin", "nox_adb.exe"),
                os.path.join(prog_files, "BlueStacks_nxt", "HD-Adb.exe"),
                os.path.join(prog_x86, "BlueStacks_nxt", "HD-Adb.exe"),
                os.path.join(prog_files, "MuMuPlayer-12.0", "shell", "adb.exe"),
                os.path.join(r"D:\leidian\LDPlayer9", "adb.exe"),
                r"C:\platform-tools\adb.exe",
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
        for unix_path in ("/usr/bin/adb", "/usr/local/bin/adb", "/opt/android-sdk/platform-tools/adb"):
            if os.path.exists(unix_path):
                return unix_path
        return "adb"

    def is_adb_available(self) -> bool:
        if not self.adb_bin:
            return False
        if os.path.isabs(self.adb_bin):
            return os.path.isfile(self.adb_bin)
        return shutil.which(self.adb_bin) is not None

    def run_cmd(self, args: List[str], device_id: Optional[str] = None, timeout: int = 15) -> Tuple[int, str, str]:
        if not self.is_adb_available():
            return -1, "", "ADB binary not found."
        
        cmd = [self.adb_bin]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(args)
        
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except subprocess.TimeoutExpired:
            return -2, "", "Command timed out."
        except Exception as e:
            return -3, "", str(e)

    # --- the adb server's own socket (no adb.exe process, so no console window and no cost for the frequent device check) ---
    SERVER = ("127.0.0.1", 5037)

    def _server_session(self, *commands: str, until_eof: bool = False) -> str:
        """Send commands one after another to the adb server (the last one's answer is returned); starts the server when it is not running."""
        for attempt in (0, 1):
            try:
                with socket.create_connection(self.SERVER, timeout=5) as s:
                    s.settimeout(10)
                    answer = b""
                    for command in commands:
                        s.sendall(f"{len(command.encode()):04x}{command}".encode())
                        status = self._read_exact(s, 4)
                        if status != b"OKAY":
                            size = int(self._read_exact(s, 4) or b"0", 16)
                            raise RuntimeError(self._read_exact(s, size).decode(errors="replace"))
                    if until_eof:
                        while chunk := s.recv(65536):
                            answer += chunk
                    else:
                        answer = self._read_exact(s, int(self._read_exact(s, 4), 16))
                    return answer.decode(errors="replace")
            except OSError:
                if attempt or not self.is_adb_available():
                    raise
                subprocess.run([self.adb_bin, "start-server"], capture_output=True, timeout=30)
                self.started_server = True
        return ""

    @staticmethod
    def _read_exact(s: socket.socket, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = s.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def stop_server_if_started(self) -> None:
        """On quitting: an adb server this program started is stopped with it (one the user was already running is left alone).
        The adb in the program's own data folder is always ours: any adb command may have started its server."""
        ours = bool(local_adb()) and os.path.normcase(os.path.abspath(self.adb_bin)) == os.path.normcase(os.path.abspath(local_adb()))
        if (self.started_server or ours) and self.is_adb_available():
            subprocess.run([self.adb_bin, "kill-server"], capture_output=True, timeout=5)

    def get_devices(self) -> List[Dict[str, str]]:
        """
        Returns list of connected ADB devices with status and model name.
        """
        if not self.is_adb_available():
            return []
        try:
            out = self._server_session("host:devices-l")
        except Exception:
            code, out, err = self.run_cmd(["devices", "-l"])
            if code != 0:
                return []
            out = "\n".join(out.splitlines()[1:])  # (the command line prints a header first)
        
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                dev_id = parts[0]
                status = parts[1]
                model = "Unknown"
                product = "Unknown"
                
                model_match = re.search(r'model:(\S+)', line)
                if model_match:
                    model = model_match.group(1).replace('_', ' ')
                prod_match = re.search(r'product:(\S+)', line)
                if prod_match:
                    product = prod_match.group(1)

                devices.append({
                    "id": dev_id,
                    "status": status,
                    "model": model,
                    "product": product,
                    "raw": line
                })
        return devices

    def check_game_installed(self, device_id: str) -> bool:
        """Whether the game is on the phone; remembered for a minute, because the device list is refreshed every few seconds."""
        cached = self._game_installed.get(device_id)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        try:
            installed = PACKAGE_NAME in self._server_session(f"host:transport:{device_id}", f"shell:pm list packages {PACKAGE_NAME}", until_eof=True)
        except Exception:
            code, out, _ = self.run_cmd(["shell", f"pm list packages {PACKAGE_NAME}"], device_id)
            installed = code == 0 and PACKAGE_NAME in out
        self._game_installed[device_id] = (time.monotonic(), installed)
        return installed

    def test_cache_access(self, device_id: str) -> Tuple[bool, str]:
        """
        Check if ADB has write access to the UnityCache directory.
        """
        test_dir = f"{REMOTE_CACHE_DIR}/.bd2_test"
        code, _, err = self.run_cmd(["shell", f"mkdir -p '{test_dir}' && rmdir '{test_dir}'"], device_id)
        if code == 0:
            return True, "Writable"
        return False, err or "Cannot write to /Android/data directory via ADB."

    def list_cached_bundles(self, device_id: str) -> List[Dict[str, str]]:
        """
        Lists existing bundles in phone's UnityCache/Shared/
        """
        code, out, _ = self.run_cmd(["shell", f"ls -1 '{REMOTE_CACHE_DIR}'"], device_id)
        if code != 0 or not out:
            return []
        
        bundles = []
        for name in out.splitlines():
            name = name.strip()
            if not name:
                continue
            # Get hash folder inside
            code_h, out_h, _ = self.run_cmd(["shell", f"ls -1 '{REMOTE_CACHE_DIR}/{name}'"], device_id)
            if code_h == 0 and out_h:
                hashes = [h.strip() for h in out_h.splitlines() if h.strip()]
                for h in hashes:
                    bundles.append({"name": name, "hash": h})
        return bundles

    def pull_bundle(self, device_id: str, bundle_name: str, bundle_hash: str, local_dest: str) -> Tuple[bool, str]:
        remote_data = f"{REMOTE_CACHE_DIR}/{bundle_name}/{bundle_hash}/__data"
        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        code, out, err = self.run_cmd(["pull", remote_data, local_dest], device_id, timeout=120)
        if code == 0:
            return True, f"Pulled {bundle_name} to {local_dest}"
        return False, err or out

    @staticmethod
    def _remote_bundle_dir(bundle_name: str, bundle_hash: str) -> Optional[str]:
        """The folder of a bundle in the game's cache on the phone; None when a name could point outside it."""
        if any(not value or value in (".", "..") or "/" in value or "\\" in value or "\x00" in value for value in (bundle_name, bundle_hash)):
            return None
        return f"{REMOTE_CACHE_DIR}/{bundle_name}/{bundle_hash}"

    def push_modded_bundle(
        self, 
        device_id: str, 
        local_data_path: str, 
        bundle_name: str, 
        bundle_hash: str, 
        backup_original: bool = True,
        progress_callback = None
    ) -> Tuple[bool, str]:
        """
        Pushes the repacked __data directly into the game's UnityCache folder.
        """
        if not os.path.isfile(local_data_path) or os.path.getsize(local_data_path) == 0:
            return False, f"Local repacked file not found: {local_data_path}"
        
        remote_bundle_dir = self._remote_bundle_dir(bundle_name, bundle_hash)
        if not remote_bundle_dir:
            return False, "Invalid bundle name or hash"
        remote_target = f"{remote_bundle_dir}/__data"
        remote_backup = f"{remote_bundle_dir}/__data.bak"

        if progress_callback:
            progress_callback(f"Ensuring remote directory exists: {remote_bundle_dir}")

        code, _, err = self.run_cmd(["shell", f"mkdir -p {shlex.quote(remote_bundle_dir)}"], device_id)
        if code != 0:
            return False, f"Failed to create remote directory: {err}"

        remote_stage = f"{remote_bundle_dir}/__data.bd2-{uuid.uuid4().hex}.tmp"
        target_q, backup_q, stage_q = map(shlex.quote, (remote_target, remote_backup, remote_stage))
        if backup_original:
            if progress_callback:
                progress_callback("Ensuring original bundle backup exists...")
            backup_cmd = f"if [ -f {target_q} ] && [ ! -f {backup_q} ]; then cp {target_q} {backup_q}; fi"
            code, out, err = self.run_cmd(["shell", backup_cmd], device_id)
            if code != 0:
                return False, f"Backup failed; installation stopped: {err or out}"

        if progress_callback:
            progress_callback(f"Transferring repacked bundle ({os.path.getsize(local_data_path) // 1024} KB)...")
        code, out, err = self.run_cmd(["push", local_data_path, remote_stage], device_id, timeout=180)
        if code != 0:
            self.run_cmd(["shell", f"rm -f {stage_q}"], device_id)
            return False, err or out

        # Rename within the same remote directory only after a complete upload.
        code, out, err = self.run_cmd(["shell", f"mv -f {stage_q} {target_q}"], device_id)
        if code != 0:
            self.run_cmd(["shell", f"rm -f {stage_q}"], device_id)
            return False, f"Could not publish uploaded bundle: {err or out}"
        if progress_callback:
            progress_callback("File transferred successfully to game directory!")
        return True, f"Mod installed to {remote_target}"

    def restore_backup(self, device_id: str, bundle_name: str, bundle_hash: str) -> Tuple[bool, str]:
        remote_bundle_dir = self._remote_bundle_dir(bundle_name, bundle_hash)
        if not remote_bundle_dir:
            return False, "Invalid bundle name or hash"
        remote_target = f"{remote_bundle_dir}/__data"
        remote_backup = f"{remote_bundle_dir}/__data.bak"

        code, out, err = self.run_cmd(["shell", f"[ -f {shlex.quote(remote_backup)} ] && cp {shlex.quote(remote_backup)} {shlex.quote(remote_target)} && rm {shlex.quote(remote_backup)} && echo RESTORED"], device_id)
        if code == 0 and "RESTORED" in out:
            return True, "Original bundle restored."
        return False, "No backup found or restore failed."

    def list_backups(self, device_id: str) -> List[Dict[str, object]]:
        """The `__data.bak` copies the manager made of original bundles before overwriting them: bundle name, hash, size in bytes, modified time."""
        code, out, _ = self.run_cmd(["shell", f"find {shlex.quote(REMOTE_CACHE_DIR)} -name __data.bak -exec stat -c '%n|%s|%Y' {{}} +"], device_id, timeout=30)
        if code != 0:
            return []
        backups = []
        for line in out.splitlines():
            path, _, rest = line.strip().partition("|")
            size, _, modified = rest.partition("|")
            parts = path.split("/")
            if len(parts) >= 3 and parts[-1] == "__data.bak" and size.isdigit() and modified.isdigit():
                backups.append({"bundle_name": parts[-3], "bundle_hash": parts[-2], "size": int(size), "modified": int(modified)})
        return sorted(backups, key=lambda b: (b["bundle_name"], b["bundle_hash"]))

    def delete_backup(self, device_id: str, bundle_name: str, bundle_hash: str) -> Tuple[bool, str]:
        """Remove a backup; the installed (modded) bundle stays as it is."""
        remote_bundle_dir = self._remote_bundle_dir(bundle_name, bundle_hash)
        if not remote_bundle_dir:
            return False, "Invalid bundle name or hash"
        backup = shlex.quote(f"{remote_bundle_dir}/__data.bak")
        code, out, err = self.run_cmd(["shell", f"[ -f {backup} ] && rm {backup} && echo DELETED"], device_id)
        return (True, "Backup deleted.") if code == 0 and "DELETED" in out else (False, "No backup found or it could not be deleted.")
