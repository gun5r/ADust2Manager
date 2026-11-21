"""Where the program's files live.

APP_DIR holds what ships with the program and is only read (the built UI, bin/, web/static). DATA_DIR holds everything the program
writes (settings, database, work/, the Spine player, tables built from the game). From source both are the project folder; the
packaged program keeps APP_DIR inside its bundle and DATA_DIR in a `data` folder next to the executable, so deleting the program
folder removes everything. BD2_DATA_DIR overrides DATA_DIR.
"""
import os
import sys
import tempfile

FROZEN = bool(getattr(sys, "frozen", False))
APP_VERSION = "0.2.0"
if FROZEN:
    APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    HOME_DIR = os.path.dirname(sys.executable)  # the folder the program was unpacked to
    DATA_DIR = os.path.join(HOME_DIR, "data")
else:
    APP_DIR = HOME_DIR = DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.environ.get("BD2_DATA_DIR") or DATA_DIR)
MODS_DIR = os.path.join(HOME_DIR, "Mods")  # created once, on the very first start, as the first mod folder
TEMP_DIR = os.path.join(DATA_DIR, "tmp")

STATIC_DIR = os.path.join(APP_DIR, "web", "static")
FRONTEND_DIST = os.path.join(APP_DIR, "frontend", "dist")
LIBS_DIR = os.path.join(DATA_DIR, "libs")  # the Spine player, fetched on first start
GENERATED_DIR = os.path.join(DATA_DIR, "generated")  # dating rules / sound events / scene costumes, built by Tools > Initial Setup
TOOLS_DIR = os.path.join(DATA_DIR, "platform-tools")  # adb, when the program had to download it
os.makedirs(TEMP_DIR, exist_ok=True)
tempfile.tempdir = TEMP_DIR  # portable: nothing is written outside the program's folder, temporary files included


def bin_path(name: str) -> str:
    """A helper executable shipped in bin/ (a `.exe` is added on Windows)."""
    return os.path.join(APP_DIR, "bin", name + (".exe" if os.name == "nt" else ""))


def helper_command(module: str) -> list:
    """Command line that runs core/<module>.py as a stand-alone helper process (the packaged program has no Python to call)."""
    if FROZEN:
        return [sys.executable, "--helper", module]
    return [sys.executable, "-I", os.path.join(APP_DIR, "core", module + ".py")]


if os.name == "nt":
    import subprocess

    _popen_init = subprocess.Popen.__init__

    def _popen_without_window(self, *args, **kwargs):
        """Every child process (adb, astcenc, helpers) starts without a console window: the program itself has none, so Windows would
        open a black window for each one and take the focus from the browser."""
        flags = kwargs.get("creationflags", 0)
        if not flags & (subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS):
            kwargs["creationflags"] = flags | subprocess.CREATE_NO_WINDOW
        _popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _popen_without_window


def clean_env() -> dict:
    """Environment for starting the user's own programs (file manager, browser): the packaged program points the library path at its
    own bundled libraries, which would break them."""
    env = dict(os.environ)
    if FROZEN and sys.platform.startswith("linux"):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
    return env
