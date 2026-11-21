"""Portraits: costume portraits from the game's CDN (one 5 MB bundle) and generated thumbnails of mods.

Mod thumbnails are PNGs the browser renders (second animation frame, see frontend ToolsModal) and uploads; they are keyed by
the mod folder and become stale when anything in the folder is newer than the thumbnail.
"""
import hashlib
import io
import json
import os
from game_info import UNITY_VERSION
from paths import helper_command
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from typing import Callable, Dict, List, Optional

from PIL import Image

import cdn_downloader

BUNDLE_KEY = "common-illustinventory"  # not the *-censorship_assets_illustinventory bundle, which the catalog lists first
MAX_PNG = 4 * 1024 * 1024
_lock = threading.Lock()


def reduction_factor(size, max_side: int) -> int:
    """Power of two (1 = leave alone) that brings the longest side of a texture to at most max_side."""
    factor = 1
    while max(size) / factor > max_side:
        factor *= 2
    return factor


_PAGE = re.compile(r"^[^:]+\.(png|jpe?g)$", re.I)
_PIXELS = re.compile(r"^(\s*)(size|bounds|offsets|xy|orig|offset):\s*(.*)$")


def reduced_atlas(text: str, folder: str, max_side: int) -> str:
    """The atlas as the shrunk textures need it: page sizes become the real reduced size and every pixel quantity of a region is
    divided by the page's factor. The skeleton keeps its original sizes, so attachments are scaled up by the ratio of the
    region's original size to the packed one (Spine's own way of using half-size atlases); the textures alone cannot be
    shrunk because mesh UVs read the real texture size."""
    from PIL import Image
    out, factor, header = [], 1, False
    for line in text.splitlines():
        stripped = line.strip()
        if _PAGE.match(stripped) and not line.startswith(" "):
            header, factor = True, 1
            try:
                with Image.open(os.path.join(folder, stripped)) as image:
                    factor = reduction_factor(image.size, max_side)
            except (OSError, ValueError):
                pass  # a missing page is left alone: the player reports it
        elif ":" not in stripped and stripped:
            header = False  # a region name: its properties follow
        match = _PIXELS.match(line)
        if match and factor > 1:
            key, values = match.group(2), [v.strip() for v in match.group(3).split(",")]
            try:
                numbers = [int(v) for v in values]
            except ValueError:
                numbers = None
            if numbers is not None:
                if key == "size" and header:
                    numbers = [-(-n // factor) for n in numbers]  # ceil: PIL's reduce() rounds sizes up
                else:
                    numbers = [round(n / factor) for n in numbers]
                line = f"{match.group(1)}{key}:{','.join(str(n) for n in numbers)}"
        out.append(line)
    return "\n".join(out) + "\n"


class Portraits:
    def __init__(self, work_dir: str):
        self.costume_dir = os.path.join(work_dir, "portraits", "costume")
        self.mod_dir = os.path.join(work_dir, "portraits", "mods")
        self.index_file = os.path.join(work_dir, "portraits", "mods.json")
        os.makedirs(self.costume_dir, exist_ok=True)
        self.texture_dir = os.path.join(work_dir, "portraits", "_textures")
        os.makedirs(self.mod_dir, exist_ok=True)
        os.makedirs(self.texture_dir, exist_ok=True)

    # ---- costume portraits -------------------------------------------------------------------------------------

    def costume_path(self, costume_id: str) -> Optional[str]:
        path = os.path.join(self.costume_dir, f"{costume_id}.png")
        return path if re.fullmatch(r"[A-Za-z0-9_]+", costume_id) and os.path.isfile(path) else None

    def update_costumes(self, manager, quality: str, log: Callable[[str], None]) -> int:
        version = cdn_downloader.get_cdn_version(quality)
        catalog, err = cdn_downloader.download_catalog(manager.cache_dir, quality, version, manager.catalog_cache, manager.catalog_lock, None)
        if not catalog:
            raise RuntimeError(f"Could not load the game catalog: {err}")
        found = cdn_downloader.find_bundle_by_key(catalog, BUNDLE_KEY)
        if not found:
            raise RuntimeError("The game catalog has no costume portrait bundle")
        key, size, bundle_hash = found
        with tempfile.TemporaryDirectory() as tmp:
            bundle = os.path.join(tmp, "illustinventory.bundle")
            log(f"Downloading costume portraits ({size / 1048576:.1f} MB)...")
            ok, error = cdn_downloader.download_catalog_file(version, quality, key, bundle_hash, size, bundle)
            if not ok:
                raise RuntimeError(f"Download failed: {error}")
            out = os.path.join(tmp, "png")
            done = subprocess.run([*helper_command("extract_costume_portraits"), bundle, out],
                                  capture_output=True, text=True, timeout=300, env={**os.environ, "BD2_UNITY_VERSION": UNITY_VERSION})
            if done.returncode:
                print(f"Portrait helper failed ({done.returncode}):\n{done.stderr}")
                raise RuntimeError(f"Could not read the portrait bundle: {done.stderr.strip().splitlines()[-1:] or 'unknown error'}")
            for name in os.listdir(out):
                shutil.move(os.path.join(out, name), os.path.join(self.costume_dir, name))
        return len(os.listdir(self.costume_dir))

    def update_extras(self, characters: List[Dict], log: Callable[[str], None]) -> int:
        """Pictures the website lists for entries that have no portrait in the game (Slap Slap Pop): each is downloaded once, as <key>.png
        next to the costume portraits, and never again while the file is there. Returns how many were fetched now."""
        fetched = 0
        for character in characters:
            for key, url in (character.get("extra_portraits") or {}).items():
                path = os.path.join(self.costume_dir, f"{key}.png")
                if os.path.isfile(path) or not re.fullmatch(r"[A-Za-z0-9_]+", key):
                    continue
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ADust2Manager)"})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        Image.open(io.BytesIO(response.read())).convert("RGB").save(path, "PNG")
                    fetched += 1
                    log(f"Portrait of {character['name']} downloaded from the website.")
                except Exception as exc:  # one missing picture must not stop the character update
                    log(f"Could not get the portrait of {character['name']}: {exc}")
        return fetched

    def delete_costumes(self) -> None:
        for name in os.listdir(self.costume_dir):
            if name.endswith(".png"):
                os.remove(os.path.join(self.costume_dir, name))

    def costume_info(self) -> Dict:
        files = [os.path.join(self.costume_dir, f) for f in os.listdir(self.costume_dir)]
        return {"count": len(files), "bytes": sum(os.path.getsize(f) for f in files),
                "updated_at": max((os.path.getmtime(f) for f in files), default=None)}

    # ---- reduced textures (portrait rendering) ----------------------------------------------------------------

    def reduced_texture(self, path: str, max_side: int) -> str:
        """A cached copy of the PNG halved until its longest side is at most max_side (or the file itself when
        it is already small). Atlas coordinates are normalised, so a smaller texture draws the same picture, only loads faster."""
        from PIL import Image
        info = os.stat(path)
        out = os.path.join(self.texture_dir, hashlib.sha1(f"{path}|{info.st_mtime_ns}|{info.st_size}|{max_side}|v4".encode("utf-8")).hexdigest() + ".png")
        if os.path.isfile(out):
            return out
        with Image.open(path) as image:
            factor = reduction_factor(image.size, max_side)
            if factor < 2:
                return path
            image.load()
            tmp = f"{out}.{threading.get_ident()}.tmp"
            image.reduce(factor).save(tmp, "PNG", compress_level=1)
        os.replace(tmp, out)
        return out

    # ---- mod thumbnails ----------------------------------------------------------------------------------------

    def _index(self) -> Dict[str, str]:
        try:
            with open(self.index_file, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _file_name(folder: str) -> str:
        return hashlib.sha1(folder.encode("utf-8")).hexdigest() + ".png"

    @staticmethod
    def _newest(folder: str) -> float:
        try:
            return max((e.stat().st_mtime for e in os.scandir(folder) if e.is_file()), default=0.0)
        except OSError:
            return 0.0

    def mod_versions(self) -> Dict[str, int]:
        """folder -> version (thumbnail mtime) for every thumbnail that is newer than its folder's files."""
        out: Dict[str, int] = {}
        for folder, name in self._index().items():
            path = os.path.join(self.mod_dir, name)
            if os.path.isfile(path) and os.path.getmtime(path) >= self._newest(folder):
                out[folder] = int(os.path.getmtime(path))
        return out

    def mod_path(self, folder: str) -> Optional[str]:
        path = os.path.join(self.mod_dir, self._file_name(folder))
        return path if os.path.isfile(path) else None

    def save_mod(self, folder: str, png: bytes) -> None:
        if len(png) > MAX_PNG or not png.startswith(b"\x89PNG"):
            raise ValueError("Not a PNG image")
        name = self._file_name(folder)
        with _lock:
            with open(os.path.join(self.mod_dir, name), "wb") as f:
                f.write(png)
            index = self._index()
            index[folder] = name
            tmp = self.index_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(index, f)
            os.replace(tmp, self.index_file)

    def mod_info(self) -> Dict:
        files = [os.path.join(self.mod_dir, f) for f in os.listdir(self.mod_dir)]
        return {"count": len(files), "bytes": sum(os.path.getsize(f) for f in files),
                "updated_at": max((os.path.getmtime(f) for f in files), default=None)}

    def delete_mods(self) -> None:
        with _lock:
            for f in os.listdir(self.mod_dir):
                os.remove(os.path.join(self.mod_dir, f))
            if os.path.isfile(self.index_file):
                os.remove(self.index_file)
            for f in os.listdir(self.texture_dir):
                os.remove(os.path.join(self.texture_dir, f))
