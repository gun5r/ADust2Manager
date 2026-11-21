"""Discover multi-mod options without hiding mixed or deeply nested variants."""
import os
import re
from pathlib import Path
from typing import Any, Optional
from mod_assets import asset_keys, directory_files, is_mod_folder


def _visible_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and is_mod_folder(path.name)


def _is_spine_directory(path: str) -> bool:
    files = directory_files(path)
    return (any(f.lower().endswith(".png") for f in files)
            and any(f.lower().endswith((".skel", ".skel.bytes", ".json", ".atlas", ".atlas.txt")) for f in files))


def _detect_spine_category(dir_path: str, fallback_name: str = "") -> str:
    """Classifies a spine mod directory by inspecting the actual skeleton and asset files inside."""
    try:
        files = [f.lower() for f in os.listdir(dir_path) if not f.startswith(".")]
    except Exception:
        files = []
    files_str = " ".join(files)
    fallback_lower = (fallback_name or "").lower()

    if "illust_dating" in files_str or "illust_dating" in fallback_lower:
        return "dating"
    if "specialillust" in files_str or "specialillust" in fallback_lower:
        return "illust"
    if any("cutscene" in f or "cut_" in f for f in files) or re.search(r'\b(cut|cutscene|skill|combat|ultimate|burst)\b', fallback_lower):
        return "cut"
    if any(re.match(r'^char\d+', f) for f in files) or re.search(r'\b(idle|lobby|field|standby|standing)\b', fallback_lower):
        return "idle"
    return "other"

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
GAME_ASSET_IMAGE = re.compile(r"(cutscene_char|char|illust_\w*|specialillust|npc|storypack)\d", re.I)
MAX_PREVIEWS = 400


def _skin_images(path: str, files: list[str]) -> set[str]:
    """Image names that are Spine texture pages: listed by an atlas, or named after a game asset."""
    skins = {f.lower() for f in files if GAME_ASSET_IMAGE.search(f)}
    for f in files:
        if f.lower().endswith((".atlas", ".atlas.txt")):
            try:
                with open(os.path.join(path, f), encoding="utf-8", errors="ignore") as fh:
                    skins.update(line.strip().lower() for line in fh if line.strip().lower().endswith(IMAGE_EXTS))
            except OSError:
                pass
    return skins


def _is_preview_name(name: str) -> bool:
    return bool(re.search(r"prev|guide|how\s*to|template|compar|readme", name, re.I))


def find_pack_previews(root: Path) -> list[dict[str, str]]:
    """Every picture in a pack that is not a skin: previews, guides, comparisons (they never carry a game asset name)."""
    found: list[dict[str, str]] = []
    skeleton_dirs: set[str] = set()  # dirs holding skeleton data: images in or below them are textures
    for dirpath, dirs, _ in os.walk(root):
        dirs[:] = sorted(d for d in dirs if is_mod_folder(d))
        files = directory_files(dirpath)
        skins = _skin_images(dirpath, files)
        if any(f.lower().endswith((".skel", ".skel.bytes", ".atlas", ".atlas.txt")) for f in files):
            skeleton_dirs.add(dirpath)
        in_project = any(d in skeleton_dirs for d in (dirpath, *map(str, Path(dirpath).parents)))
        folder = Path(dirpath).relative_to(root).as_posix()
        for f in sorted(files):
            if f.lower().endswith(IMAGE_EXTS) and f.lower() not in skins and not (in_project and not _is_preview_name(f)):
                found.append({"name": f, "folder": "" if folder == "." else folder, "rel_path": (Path(folder) / f).as_posix().removeprefix("./"),
                              "full_path": os.path.join(dirpath, f)})
        if len(found) >= MAX_PREVIEWS:
            break
    return found[:MAX_PREVIEWS]


def inspect_multi_mod_tree(folder_path: str, mod_name: Optional[str] = None) -> dict[str, Any]:
    root = Path(folder_path).absolute()
    if not root.is_dir():
        return {"error": "Folder does not exist", "categories": []}

    def relative(path: Path) -> str:
        value = path.relative_to(root).as_posix()
        return "" if value == "." else value

    def previews(path: Path) -> list[dict[str, str]]:
        return [{"name": f, "rel_path": relative(path / f), "full_path": str(path / f)}
                for f in directory_files(str(path))
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]

    def variant(path: Path, name: Optional[str] = None) -> dict[str, Any]:
        files = directory_files(str(path))
        keys = asset_keys(files)
        rel = relative(path)
        return {"id": rel, "name": name or path.name, "stem": keys[0] if keys else path.name,
                "category": _detect_spine_category(str(path), path.name),
                "rel_path": rel, "full_path": str(path), "is_folder": True,
                "size_bytes": 0, "files": files, "asset_keys": keys,
                "asset_key": keys[0] if keys else "unknown"}

    def option(path: Path, variants: list[dict[str, Any]]) -> dict[str, Any]:
        rel = relative(path)
        return {"id": rel or "root_opt", "name": path.name, "rel_path": rel,
                "full_path": str(path), "category": variants[0]["category"],
                "previews": previews(path), "variants": variants}

    def discover(path: Path) -> list[dict[str, Any]]:
        children = sorted((p for p in path.iterdir() if _visible_directory(p)), key=lambda p: p.name.lower())
        direct = [p for p in children if _is_spine_directory(str(p))]
        options = []
        if direct:
            options.append(option(path, [variant(p) for p in direct]))
        # A direct variant and a nested option can coexist under the same parent.
        for child in children:
            if child not in direct:
                options.extend(discover(child))
        return options

    try:
        children = sorted((p for p in root.iterdir() if _visible_directory(p)), key=lambda p: p.name.lower())
        if mod_name:
            prefix = mod_name.strip() + " - "
            matching = [p for p in children if p.name.startswith(prefix) and _is_spine_directory(str(p))]
            if matching:
                variants = [variant(p, p.name[len(prefix):].strip()) for p in matching]
                return {"status": "ok", "categories": [{"id": "root", "name": mod_name,
                        "rel_path": "", "full_path": str(root), "previews": [],
                        "options": [option(root, variants)]}],
                        "previews": find_pack_previews(root)}

        categories = []
        direct = [p for p in children if _is_spine_directory(str(p))]
        if direct:
            categories.append({"id": "root", "name": root.name, "rel_path": "",
                               "full_path": str(root), "previews": [],
                               "options": [option(root, [variant(p) for p in direct])]})
        for child in children:
            if child in direct:
                continue
            options = discover(child)
            if options:
                categories.append({"id": relative(child), "name": child.name,
                                   "rel_path": relative(child), "full_path": str(child),
                                   "previews": previews(child), "options": options})
        return {"status": "ok", "categories": categories, "previews": find_pack_previews(root)}
    except OSError as exc:
        return {"error": f"Cannot inspect mod folder: {exc}", "categories": []}
