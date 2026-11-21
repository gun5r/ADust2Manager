"""Google's platform-tools (adb) for people who do not have it: downloaded on request into the data folder."""
import os
import stat
import tempfile
import zipfile
from typing import Callable, Optional

import requests

from paths import DATA_DIR, TOOLS_DIR

URL = "https://dl.google.com/android/repository/platform-tools-latest-{}.zip"


def local_adb() -> Optional[str]:
    path = os.path.join(TOOLS_DIR, "adb.exe" if os.name == "nt" else "adb")
    return path if os.path.isfile(path) else None


def install(progress: Callable[[str], None] = lambda _: None) -> str:
    """Download and unpack platform-tools; returns the path of adb."""
    url = URL.format("windows" if os.name == "nt" else "linux")
    progress(f"Downloading platform-tools from {url} ...")
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, "platform-tools.zip")
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in response.iter_content(1 << 20):
                    f.write(chunk)
        with zipfile.ZipFile(archive) as z:
            root = os.path.realpath(DATA_DIR)
            for member in z.namelist():  # the archive's folder is "platform-tools/"
                if not os.path.realpath(os.path.join(root, member)).startswith(root + os.sep):
                    raise RuntimeError("The platform-tools archive holds an unexpected path")
            z.extractall(root)
    path = local_adb()
    if not path:
        raise RuntimeError("The platform-tools archive does not contain adb")
    if os.name != "nt":
        for name in os.listdir(TOOLS_DIR):
            file = os.path.join(TOOLS_DIR, name)
            if os.path.isfile(file) and name in ("adb", "fastboot", "etc1tool", "hprof-conv", "make_f2fs", "make_f2fs_casefold", "mke2fs", "sqlite3"):
                os.chmod(file, os.stat(file).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    progress("adb is ready.")
    return path
