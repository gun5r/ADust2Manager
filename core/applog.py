"""The log file (data/manager.log): everything the program prints with a time stamp, a start-up report on the machine, and every
uncaught error, so a failure on someone else's computer can be diagnosed from this one file."""
import datetime
import faulthandler
import os
import platform
import shutil
import subprocess
import sys
import threading
import traceback


class _Stamped:
    """A text stream that puts the time in front of each line, writes it to the log file and (from source) to the console too."""

    def __init__(self, file, console=None):
        self.file, self.console, self.at_line_start = file, console, True

    def write(self, text):
        if not text:
            return 0
        out = []
        for part in text.splitlines(keepends=True):
            if self.at_line_start:
                out.append(datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S] "))
            out.append(part)
            self.at_line_start = part.endswith("\n")
        try:
            self.file.write("".join(out))
            self.file.flush()
        except Exception:
            pass
        if self.console:
            try:
                self.console.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        try:
            self.file.flush()
        except Exception:
            pass

    def isatty(self):
        return False

    def fileno(self):  # subprocesses and faulthandler need a real descriptor
        return self.file.fileno()


def start(log_path: str, paths) -> None:
    """Redirect stdout/stderr into the log (the previous run's log is kept as manager.previous.log) and install the error hooks."""
    try:
        if os.path.isfile(log_path):
            os.replace(log_path, os.path.splitext(log_path)[0] + ".previous.log")
    except OSError:
        pass
    file = open(log_path, "w", encoding="utf-8", errors="replace", buffering=1)
    stream = _Stamped(file, console=sys.__stdout__ if not paths.FROZEN else None)
    sys.stdout = sys.stderr = stream
    faulthandler.enable(file)  # a crash inside a native library still leaves a trace

    def excepthook(kind, error, tb):
        print("UNCAUGHT ERROR:\n" + "".join(traceback.format_exception(kind, error, tb)))

    sys.excepthook = excepthook
    threading.excepthook = lambda a: print(f"UNCAUGHT ERROR in thread {a.thread.name if a.thread else '?'}:\n" + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    report(paths)


def _version_of(command) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return ((done.stdout or done.stderr).strip().splitlines() or ["(no output)"])[0]
    except Exception as e:
        return f"cannot run: {e}"


def report(paths) -> None:
    """What a bug report needs to know about the machine."""
    print(f"ADust2Manager {paths.APP_VERSION} ({'packaged' if paths.FROZEN else 'from source'})")
    print(f"System: {platform.platform()} | {platform.machine()} | Python {platform.python_version()}")
    print(f"Executable: {sys.executable}")
    print(f"Program folder: {paths.HOME_DIR}\nData folder: {paths.DATA_DIR}\nMods folder (created on the very first start): {paths.MODS_DIR}")
    try:
        probe = os.path.join(paths.DATA_DIR, ".write-test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        print("Data folder is writable: yes")
    except OSError as e:
        print(f"Data folder is writable: NO ({e})")
    print(f"Free space in the data folder: {shutil.disk_usage(paths.DATA_DIR).free / 1e9:.1f} GB")
    astc = paths.bin_path("astcenc")
    astc = astc if os.path.isfile(astc) else shutil.which("astcenc")
    print(f"astcenc: {astc} -> {_version_of([astc, '-version']) if astc else 'NOT FOUND'}")
    from adb_install import local_adb
    adb = shutil.which("adb") or local_adb()
    print(f"adb: {adb} -> {_version_of([adb, 'version']) if adb else 'not found (Tools > Phone Connection can download it)'}")
    print(f"Spine player downloaded: {os.path.isfile(os.path.join(paths.LIBS_DIR, 'spine-player.js'))}")
    print(f"Built UI present: {os.path.isfile(os.path.join(paths.FRONTEND_DIST, 'index.html'))}")
    print("-" * 60)
