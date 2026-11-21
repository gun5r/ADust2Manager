"""Damaged mod files: downloads cut off half-way leave PNG textures without their end (rows of the picture are simply missing, so parts of the
model vanish) and skeletons that stop in the middle. Nothing complains about them later (the image decoder is told to accept them), so the
mod just looks broken; this finds them first."""
import os

import skel_convert
import skel_files

PNG_END = b"IEND\xaeB`\x82"


def png_complete(path: str) -> bool:
    """A PNG file ends with its IEND chunk; a cut-off download does not."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - 16))
            return PNG_END in f.read()
    except OSError:
        return False


def _files(folder: str, suffixes: tuple):
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        if name.lower().endswith(suffixes) and not name.startswith(".") and os.path.isfile(path):
            yield name, path


def damaged_textures(folder: str) -> list:
    return [{"file": name, "reason": "The picture file is cut off (an incomplete download): parts of the model that were stored in its missing rows will not show."}
            for name, path in _files(folder, (".png",)) if not png_complete(path)]


def damaged_skeletons(folder: str, cache_dir: str | None = None) -> list:
    """4.1 skeletons the converter cannot read to the end. Reading one converts it, so with a `cache_dir` a preview of the same file is free afterwards."""
    found = []
    for name, path in _files(folder, (".skel", ".skel.bytes")):
        try:
            skel_files.current_bytes(path, cache_dir)
        except skel_convert.SkelError as e:
            found.append({"file": name, "reason": f"The skeleton file is cut off or damaged ({e})."})
        except OSError:
            pass
    return found


def damaged_files(folder: str, cache_dir: str | None = None) -> list:
    """[{file, reason}] for the textures and skeletons of one mod folder that are cut off."""
    return damaged_textures(folder) + damaged_skeletons(folder, cache_dir)
