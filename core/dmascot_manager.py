import os
import sys
import json
import time
import subprocess
import shutil
import signal
import atexit
from typing import Dict, Any, Optional, Tuple

class DMascotManager:
    """Manages Desktop Mascot instances across Linux (KDE Plasma/KWin) and Windows."""

    def __init__(self, port: int = 8082):
        self.port = port
        self.mascots: Dict[str, Dict[str, Any]] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        # Clean any zombie orphan processes left over from prior runs immediately on start
        self.kill_all_zombies()

    def kill_all_zombies(self):
        """Scans /proc and kills any lingering orphan mascot processes to stop 404 polling."""
        if not sys.platform.startswith("linux"):
            return
        my_pid = os.getpid()
        try:
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                pid = int(entry)
                if pid == my_pid:
                    continue
                try:
                    cmdline_path = f"/proc/{pid}/cmdline"
                    if not os.path.exists(cmdline_path):
                        continue
                    with open(cmdline_path, "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore").replace("\x00", " ")
                    if "dmascot_qt_window.py" in cmdline or "dmascot_window.py" in cmdline:
                        os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
        except Exception:
            pass

    def get_all(self) -> list:
        dead_ids = []
        for mid, proc in self.processes.items():
            if proc.poll() is not None:
                dead_ids.append(mid)
        for mid in dead_ids:
            self.processes.pop(mid, None)
            self.mascots.pop(mid, None)
        return list(self.mascots.values())

    def get(self, mid: str) -> Optional[Dict[str, Any]]:
        return self.mascots.get(mid)

    def launch(self, mod_data: Dict[str, Any]) -> Dict[str, Any]:
        mid = f"mascot_{int(time.time() * 1000)}"
        mascot_info = {
            "id": mid,
            "mod_name": mod_data.get("mod_name") or mod_data.get("name") or "Mascot",
            "character": mod_data.get("character") or "Others",
            "folder_path": mod_data.get("folder_path") or "",
            "files": mod_data.get("files") or [],
            "asset_stem": mod_data.get("asset_stem") or "",
            "category": mod_data.get("category") or "idle",
            "is_multi": bool(mod_data.get("is_multi")),
            "variant_path": mod_data.get("variant_path") or "",
            "draggable": True,
            "locked": False,
            "click_through": False,
            "layer": "above",  # "above" or "below"
            "scale": 1.0,
            "opacity": 1.0,
            "status": "running",
            "created_at": time.time()
        }
        self.mascots[mid] = mascot_info

        url = f"http://127.0.0.1:{self.port}/static/mascot.html?id={mid}"
        self._spawn_window(mid, mascot_info, url)
        return mascot_info

    def update(self, mid: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mascot = self.mascots.get(mid)
        if not mascot:
            return None
        mascot.update(patch)
        return mascot

    def close(self, mid: str) -> bool:
        mascot = self.mascots.get(mid)
        if not mascot and mid not in self.processes:
            return False

        if mascot:
            mascot["status"] = "closed"

        proc = self.processes.pop(mid, None)
        if proc:
            try:
                if sys.platform.startswith("linux"):
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    if sys.platform.startswith("linux"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                except Exception:
                    pass

        self.mascots.pop(mid, None)
        return True

    def close_all(self):
        for mid in list(self.mascots.keys()):
            self.close(mid)
        for mid in list(self.processes.keys()):
            self.close(mid)
        self.kill_all_zombies()

    def _spawn_window(self, mid: str, info: Dict[str, Any], url: str):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dmascot_window.py")
        args = [sys.executable, script_path, mid, url]
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work")
            os.makedirs(log_dir, exist_ok=True)
            log_fp = open(os.path.join(log_dir, "dmascot.log"), "a", encoding="utf-8")
            
            kwargs = {"stdout": log_fp, "stderr": log_fp}
            if sys.platform.startswith("linux"):
                kwargs["start_new_session"] = True

            p = subprocess.Popen(args, **kwargs)
            self.processes[mid] = p
        except Exception as e:
            print(f"[DMascot] Spawn error: {e}", file=sys.stderr)

    def install_kwin_window_rule(self) -> Tuple[bool, str]:
        """
        Adds or updates the BD2_Mascot KWin Window Rule in ~/.config/kwinrulesrc.
        Only executed on-demand when explicitly triggered from the UI.
        """
        config_path = os.path.expanduser("~/.config/kwinrulesrc")
        py_class = f"python{sys.version_info.major}.{sys.version_info.minor} python{sys.version_info.major}"

        rule_kv_lines = [
            "Description=Preferencias de la ventana de BD2_Mascot",
            "above=true",
            "aboverule=2",
            "acceptfocusrule=2",
            "layer=osd",
            "layerrule=2",
            "noborder=true",
            "noborderrule=2",
            "position=0,0",
            "positionrule=4",
            "title=BD2_Mascot",
            "titlematch=1",
            "types=1",
            f"wmclass={py_class}",
            "wmclasscomplete=true",
            "wmclassmatch=1"
        ]

        if not os.path.exists(config_path):
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                content = "[General]\nrules=bd2_mascot\n\n[bd2_mascot]\n" + "\n".join(rule_kv_lines) + "\n"
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, "Configured BD2_Mascot window rule in ~/.config/kwinrulesrc!"
            except Exception as e:
                return False, f"Error writing kwinrulesrc: {e}"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_lines = f.read().splitlines()

            # Parse existing file into ordered list of (section_name, [line_strings])
            sections = []
            curr_sec = None
            curr_lines = []

            for line in raw_lines:
                sline = line.strip()
                if sline.startswith("[") and sline.endswith("]"):
                    if curr_sec is not None:
                        sections.append((curr_sec, curr_lines))
                    curr_sec = sline[1:-1].strip()
                    curr_lines = []
                else:
                    curr_lines.append(line)
            if curr_sec is not None:
                sections.append((curr_sec, curr_lines))

            # Ensure [General] has rules= containing bd2_mascot without duplicating
            general_idx = -1
            for idx, (sec_name, _) in enumerate(sections):
                if sec_name.lower() == "general":
                    general_idx = idx
                    break

            if general_idx == -1:
                sections.insert(0, ("General", ["rules=bd2_mascot"]))
            else:
                sec_name, sec_lines = sections[general_idx]
                rules_found = False
                new_sec_lines = []
                for sl in sec_lines:
                    if sl.strip().startswith("rules="):
                        curr_rules = [r.strip() for r in sl.strip().split("=")[1].split(",") if r.strip()]
                        if "bd2_mascot" not in curr_rules:
                            curr_rules.append("bd2_mascot")
                        new_sec_lines.append(f"rules={','.join(curr_rules)}")
                        rules_found = True
                    else:
                        new_sec_lines.append(sl)
                if not rules_found:
                    new_sec_lines.append("rules=bd2_mascot")
                sections[general_idx] = (sec_name, new_sec_lines)

            # Insert or cleanly replace [bd2_mascot] section
            bd2_idx = -1
            for idx, (sec_name, _) in enumerate(sections):
                if sec_name == "bd2_mascot":
                    bd2_idx = idx
                    break

            if bd2_idx != -1:
                sections[bd2_idx] = ("bd2_mascot", rule_kv_lines)
            else:
                sections.append(("bd2_mascot", rule_kv_lines))

            # Reconstruct clean INI content
            output_parts = []
            for sec_name, sec_lines in sections:
                clean_lines = [l for l in sec_lines if l.strip()]
                output_parts.append(f"[{sec_name}]\n" + "\n".join(clean_lines))

            new_content = "\n\n".join(output_parts).strip() + "\n"

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Reload KWin rules via qdbus if available
            try:
                subprocess.run(["qdbus", "org.kde.KWin", "/KWin", "reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            except Exception:
                pass

            return True, "Successfully configured BD2_Mascot window rule in ~/.config/kwinrulesrc!"
        except Exception as e:
            return False, f"Error writing kwinrulesrc: {e}"

dmascot_mgr = DMascotManager()
atexit.register(dmascot_mgr.close_all)
