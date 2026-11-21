"""Shared filesystem metadata for loose Spine mods."""
import hashlib
import os
import re
from pathlib import Path

import skel_convert

ASSET_PATTERN = re.compile(
    r"cutscene_char\d{4,6}|char\d{4,6}|illust_dating\d+|illust_special\d+|"
    r"illust_talk\d+|npc\d+|specialillust\w+|storypack\w+", re.I
)
ASSET_SUFFIX = re.compile(r"\.(?:skel\.bytes|atlas\.txt|skel|atlas|json|png)$", re.I)


def asset_keys(files: list[str]) -> list[str]:
    """Return all replacement targets, keeping animation types and dating IDs distinct."""
    keys = set()
    has_spine = any(f.lower().endswith((".skel", ".skel.bytes", ".atlas", ".atlas.txt", ".json")) for f in files)
    for filename in files:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if not ASSET_SUFFIX.search(name):
            continue
        match = ASSET_PATTERN.search(name)
        if match:
            keys.add(match.group())
        elif not name.endswith(".png") or not has_spine:
            stem = ASSET_SUFFIX.sub("", name)
            stem = re.sub(r"_(?:hd|uhd|opt)$", "", stem)
            # Numbered PNG pages belong to one skeleton, not separate targets.
            if name.endswith(".png"):
                stem = re.sub(r"_\d+$", "", stem)
            keys.add(stem)
    return sorted(keys)


def directory_files(path: str) -> list[str]:
    return sorted(entry.name for entry in Path(path).iterdir()
                  if entry.is_file() and not entry.name.startswith("."))


def is_mod_folder(name: str) -> bool:
    """False for the folders that are never mods or variants: hidden ones (`.old`, `.spine41`, ...) and anything marked .old or .bak, in any case."""
    low = name.lower()
    return not name.startswith(".") and ".old" not in low and ".bak" not in low


def source_fingerprint(folders: list[str]) -> str:
    """Identify source paths and contents; timestamps alone can miss edited assets."""
    digest = hashlib.sha256()
    digest.update(("skel42-" + skel_convert.REVISION).encode())  # 4.1 skeletons are converted while preparing: new converter, new repack
    for folder in folders:
        digest.update(os.path.normcase(os.path.realpath(folder)).encode("utf-8"))
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if is_mod_folder(d))
            for name in sorted(files):
                if not ASSET_SUFFIX.search(name) or name.startswith("."):
                    continue
                path = os.path.join(root, name)
                digest.update(os.path.relpath(path, folder).replace(os.sep, "/").encode("utf-8"))
                with open(path, "rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
    return digest.hexdigest()


def _get_asset_stem(skel_files, json_files, png_files, default_name):
    for s in (skel_files or json_files):
        return re.sub(r'\.(skel|json|skel\.bytes)$', '', s.lower())
    for p in png_files:
        return re.sub(r'_\d+$', '', os.path.splitext(p)[0].lower())
    return default_name
