"""Scanning mod folders into mod records."""
import json
import multi_manager
import os
import re
import spine_merger
from collections import defaultdict
from mod_assets import _get_asset_stem, asset_keys, directory_files, is_mod_folder
from typing import Any, Dict, List, Optional, Set, Tuple


class ScannerMixin:
    def clear_scan_cache(self):
        with self.scan_cache_lock:
            self.scan_cache.clear()

    @staticmethod
    def classify_mod_category(name: str, files: List[str], is_multi: bool = False) -> Tuple[str, str, int]:
        files_str = " ".join(files).lower()
        name_lower = name.lower()
        if is_multi:
            return "multi", "Multi Mods", 0
        
        # Strict Dating Rule: ONLY mods whose mod file title is illust_dating
        if "illust_dating" in files_str or re.search(r'illust_dating\d+', name_lower):
            return "dating", "Dating Animations", 4
        elif re.search(r'specialillust', files_str) or re.search(r'specialillust', name_lower):
            return "illust", "Illustrations", 3
        elif re.search(r'\b(cut|cutscene|skill|combat|ultimate|burst)\b|_cut\b|cut_|cutscene', name_lower) or any('cutscene' in f.lower() for f in files):
            return "cut", "Cut Animations", 2
        elif re.search(r'\b(idle|lobby|field|standby)\b|_idle\b|idle_', name_lower) or any(re.match(r'^char\d+', f.lower()) for f in files) or re.search(r'char\d+', name_lower):
            return "idle", "Idle Animations", 1
        else:
            return "other", "Other Animations", 5

    def scan_mods_folder(self, mods_root: str, force_multi: bool = False, invalidate: bool = False) -> List[Dict[str, Any]]:
        """
        Scans a directory for Brown Dust 2 mod folders.
        Supports:
          1. Standard loose mod folders
          2. Multi-choice variant mods (same author/costume variants)
          3. Deeply nested library/database folders (unrolls distinct mods per character/author)
          4. Force multi flag (if marked as multichoice tab or contains .multichoice / .multi)
        """
        mods_root = os.path.abspath(mods_root)
        if not os.path.exists(mods_root):
            return []

        try:
            current_mtime = os.path.getmtime(mods_root)
        except Exception:
            current_mtime = 0

        cache_key = (mods_root, current_mtime, force_multi)
        if not invalidate and hasattr(self, "scan_cache"):
            with self.scan_cache_lock:
                if cache_key in self.scan_cache:
                    return self.scan_cache[cache_key]

        # Check for flag file in directory or parameter
        is_root_forced_multi = force_multi or os.path.exists(os.path.join(mods_root, ".multichoice")) or os.path.exists(os.path.join(mods_root, ".multi"))

        mods = []
        _classify_mod_category = self.classify_mod_category

        def _get_spine_assets_in_dir(path: str):
            """Returns (pngs, atlases, skels, jsons, all_files) in a single directory."""
            try:
                files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and not f.startswith(".")]
            except Exception:
                return [], [], [], [], []
            pngs = [f for f in files if f.lower().endswith(".png")]
            atlases = [f for f in files if f.lower().endswith((".atlas", ".atlas.txt"))]
            skels = [f for f in files if f.lower().endswith((".skel", ".skel.bytes"))]
            jsons = [f for f in files if f.lower().endswith(".json")]
            return pngs, atlases, skels, jsons, files

        def _is_spine_directory(path: str) -> bool:
            pngs, atlases, skels, jsons, _ = _get_spine_assets_in_dir(path)
            return bool(pngs and (atlases or skels or jsons))

        def _extract_author(name: str) -> Optional[str]:
            m = re.search(r"\[([^\]]+)\]", name)
            if m:
                return m.group(1).strip().lower()
            m2 = re.match(r"^\(([^)]+)\)", name)
            if m2:
                return m2.group(1).strip().lower()
            return None

        def _get_prefix(name: str):
            # Pattern 1: ModName [Author] - Variant Option
            m = re.match(r'^(.*?\[[^\]]+\])\s*-\s*(.+)$', name)
            if m:
                return m.group(1).strip(), m.group(2).strip()
            # Pattern 2: [Author] ModName - Variant Option
            m = re.match(r'^(\[[^\]]+\]\s*.+?)\s*-\s*([^-]+)$', name)
            if m:
                return m.group(1).strip(), m.group(2).strip()
            # Pattern 3: (Author) ModName - Variant Option (requires internal dash)
            m = re.match(r'^(\([^)]+\)\s*.+?)\s*-\s*([^-]+)$', name)
            if m and len(m.group(1).split(" - ")) >= 2:
                return m.group(1).strip(), m.group(2).strip()
            # Pattern 4: Multiple " - " parts, e.g. Char - Costume - Option (>= 3 parts)
            # Only if the last part is not an author tag [Author]
            parts = name.split(" - ")
            if len(parts) >= 3:
                last = parts[-1].strip()
                if not re.search(r'\[[^\]]+\]$', last):
                    pref = " - ".join(parts[:-1]).strip()
                    return pref, last
            return None, name

        GENERIC_CATEGORIES = {
            "standing", "cutscene", "cutscenes", "idle", "burst", "dating",
            "illust", "illustration", "illustrations", "character", "characters",
            "costume", "costumes", "scenes", "scene", "npc", "uncategorized",
            "default", "mods", "database", "minigame", "others"
        }

        NOT_AUTHOR_TAG = re.compile(r"cut(scene)?|idle|standing|dating|burst|skill|nsfw|sfw|hd|v?\d+|full|normal|default|alt|swap", re.I)

        def _author_tags(name: str) -> Set[str]:
            """Every [tag] / (tag) in a folder name that is not a variant label such as [Idle] or (V2)."""
            tags = {t.strip().lower() for t in re.findall(r"[\[(]([^\])]+)[\])]", name)}
            return {t for t in tags if t and not NOT_AUTHOR_TAG.fullmatch(t) and t not in GENERIC_CATEGORIES}

        def _get_all_spine_subdirs(root_path: str, max_depth: int = 6) -> List[str]:
            res = []
            try:
                for dirpath, dirs, _ in os.walk(root_path):
                    dirs[:] = [d for d in dirs if is_mod_folder(d)]
                    rel = os.path.relpath(dirpath, root_path)
                    depth = 0 if rel == "." else len(rel.split(os.sep))
                    if depth >= max_depth:
                        dirs.clear()
                    if dirpath != root_path and _is_spine_directory(dirpath):
                        res.append(dirpath)
            except Exception:
                pass
            return res

        def _extract_spine_stems(dirpath: str) -> Set[str]:
            stems = set()
            try:
                for f in os.listdir(dirpath):
                    fl = f.lower()
                    if fl.endswith((".skel", ".skel.bytes", ".atlas", ".atlas.txt", ".png")):
                        base = re.sub(r"\.(skel(\.bytes)?|atlas(\.txt)?|png)$", "", fl)
                        base = re.sub(r"^(cutscene_|burst_|illust_|scene_)", "", base)
                        base = re.sub(r"_\d+$", "", base)
                        stems.add(base)
            except Exception:
                pass
            return stems

        def _is_multi_mod_directory(entry_path: str, parent_path: str) -> bool:
            name_lower = os.path.basename(entry_path).lower()
            parent_lower = os.path.basename(parent_path).lower()
            root_lower = os.path.basename(mods_root).lower()

            # Rule 1: Negative overrides (_n, _normal, -n, -normal, .nomulti, .normal, .single)
            if name_lower.endswith(("_n", "_normal", "-n", "-normal")) or parent_lower.endswith(("_n", "_normal", "-n", "-normal")):
                return False
            if os.path.exists(os.path.join(entry_path, ".normal")) or os.path.exists(os.path.join(entry_path, ".nomulti")) or os.path.exists(os.path.join(entry_path, ".single")):
                return False

            # Rule 2: Positive overrides (_m, _multi, -m, -multi, .multi, .multichoice)
            if name_lower.endswith(("_m", "_multi", "-m", "-multi")):
                return True
            if parent_lower.endswith(("_m", "_multi", "-m", "-multi")) or (root_lower.endswith(("_m", "_multi", "-m", "-multi")) and parent_path == mods_root):
                return True
            if os.path.exists(os.path.join(entry_path, ".multi")) or os.path.exists(os.path.join(entry_path, ".multichoice")):
                return True

            # Rule 3: Generic category folder names are NEVER multi-mods
            clean_name = re.sub(r"^[\d\s._-]+", "", name_lower)
            clean_name = re.sub(r"[\d\s._-]+$", "", clean_name)
            if name_lower in GENERIC_CATEGORIES or clean_name in GENERIC_CATEGORIES:
                return False

            # Rule 4: Check immediate child directories
            try:
                child_entries = [e for e in os.scandir(entry_path) if e.is_dir() and is_mod_folder(e.name)]
            except Exception:
                return False

            if not child_entries:
                return False

            # If checking mods_root itself, verify it is not a container of distinct mods with suffixes
            if entry_path == mods_root and not (is_root_forced_multi or name_lower.endswith(("_m", "_multi", "-m", "-multi"))):
                has_child_overrides = any(
                    e.name.lower().endswith(("_n", "_normal", "-n", "-normal", "_m", "_multi", "-m", "-multi"))
                    for e in child_entries
                )
                if has_child_overrides:
                    return False

            child_names = [e.name for e in child_entries]

            # Rule 5: Multi-author detection
            # If child folders contain 2 or more distinct [Author] tags, it is a category/database folder
            authors = set()
            for n in child_names:
                auth = _extract_author(n)
                if auth:
                    authors.add(auth)
            if len(authors) >= 2:
                return False

            # Rule 6: Structural spine variants & asset stem consistency
            # A variant folder marked .normal/.nomulti/.single is a mod of its own, not an option of this one.
            spine_subdirs = [d for d in _get_all_spine_subdirs(entry_path, max_depth=6)
                             if not any(os.path.exists(os.path.join(d, marker)) for marker in (".normal", ".nomulti", ".single"))]
            if len(spine_subdirs) < 2:
                return False

            # Variants of one multi-mod come from one author. Several authors anywhere below means a
            # container (e.g. a costume folder holding Standing/ and Cutscene/ mods from different people).
            deep_authors = set()
            for sdir in spine_subdirs:
                deep_authors |= _author_tags(os.path.basename(sdir))
            if len(deep_authors) >= 2:
                return False

            all_stems = set()
            for sdir in spine_subdirs:
                all_stems.update(_extract_spine_stems(sdir))

            # In a multi-mod, variants target the SAME character/costume asset stem(s)
            # (Typically 1 normalized stem like char000707, at most 3 if char + cutscene + burst)
            if len(all_stems) > 3:
                return False

            return True

        # Check if mods_root itself is a direct spine directory
        root_pngs, root_atlases, root_skels, root_jsons, root_files = _get_spine_assets_in_dir(mods_root)
        try:
            sub_dirs = [e for e in os.scandir(mods_root) if e.is_dir() and is_mod_folder(e.name)]
        except Exception:
            sub_dirs = []

        if root_pngs and (root_atlases or root_skels or root_jsons) and not sub_dirs:
            stem = _get_asset_stem(root_skels, root_jsons, root_pngs, os.path.basename(mods_root))
            c_key, c_name, c_order = _classify_mod_category(os.path.basename(mods_root), root_files, False)
            mods.append({
                "id": os.path.basename(mods_root),
                "name": os.path.basename(mods_root),
                "folder_name": os.path.basename(mods_root),
                "folder_path": mods_root,
                "asset_stem": stem,
                "category": c_key,
                "category_name": c_name,
                "category_order": c_order,
                "files": sorted(root_files),
                "png_files": sorted(root_pngs),
                "atlas_files": sorted(root_atlases),
                "skel_files": sorted(root_skels),
                "json_files": sorted(root_jsons),
                "archive_files": [],
                "is_multi": False,
                "texture_count": len(root_pngs),
                "has_json_anim": len(root_jsons) > 0 and len(root_skels) == 0,
                "has_backup": spine_merger.has_backup(mods_root),
            })
            for m in mods:
                m["asset_key"] = self.extract_mod_asset_key(m)
                m["asset_keys"] = asset_keys(m.get("files") or [])
            return mods

        # If mods_root itself is a multi-mod (e.g. named Something_multi or inside 1Batch)
        if _is_multi_mod_directory(mods_root, os.path.dirname(mods_root)) and not _is_spine_directory(mods_root):
            png_previews = []
            try:
                for root, _, files in os.walk(mods_root):
                    for f in files:
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and not f.startswith("."):
                            png_previews.append(f)
                        if len(png_previews) >= 10:
                            break
                    if len(png_previews) >= 10:
                        break
            except Exception:
                pass
            root_name = os.path.basename(mods_root)
            mods.append({
                "id": root_name,
                "name": root_name,
                "folder_name": root_name,
                "folder_path": mods_root,
                "asset_stem": root_name,
                "category": "multi",
                "category_name": "Multi Mods",
                "category_order": 0,
                "files": [],
                "png_files": sorted(png_previews),
                "atlas_files": [],
                "skel_files": [],
                "json_files": [],
                "archive_files": [],
                "is_multi": True,
                "texture_count": len(png_previews),
                "has_json_anim": False,
                "has_backup": spine_merger.has_backup(mods_root),
            })
            for m in mods:
                m["asset_key"] = self.extract_mod_asset_key(m)
                m["asset_keys"] = asset_keys(m.get("files") or [])
            return mods

        def _scan_directory(curr: str):
            try:
                entries = [e for e in os.scandir(curr) if e.is_dir() and is_mod_folder(e.name)]
            except Exception:
                return

            spine_subdirs = []
            non_spine_subdirs = []

            for e in entries:
                if _is_spine_directory(e.path):
                    spine_subdirs.append(e)
                else:
                    non_spine_subdirs.append(e)

            if spine_subdirs:
                curr_name_lower = os.path.basename(curr).lower()
                is_curr_forced_normal = (
                    curr_name_lower.endswith(("_n", "_normal", "-n", "-normal"))
                    or os.path.exists(os.path.join(curr, ".normal"))
                    or os.path.exists(os.path.join(curr, ".nomulti"))
                    or os.path.exists(os.path.join(curr, ".single"))
                )

                # Group sibling spine subdirectories sharing common prefix before " - "
                groups = defaultdict(list)
                singles = []

                if not is_curr_forced_normal:
                    for e in spine_subdirs:
                        pref, var = _get_prefix(e.name)
                        if pref:
                            groups[pref].append((e, var))
                        else:
                            singles.append(e)
                else:
                    singles = list(spine_subdirs)

                for pref, items in groups.items():
                    if len(items) >= 2:
                        # Validate no conflicting distinct author tags in the same group
                        group_authors = {_extract_author(e.name) for e, _ in items if _extract_author(e.name)}
                        if len(group_authors) > 1:
                            for e, _ in items:
                                singles.append(e)
                            continue

                        first_e, _ = items[0]
                        pngs, atlases, skels, jsons, files = _get_spine_assets_in_dir(first_e.path)
                        stem = _get_asset_stem(skels, jsons, pngs, pref)
                        c_key, c_name, c_order = "multi", "Multi Mods", 0

                        mods.append({
                            "id": pref,
                            "name": pref,
                            "folder_name": pref,
                            "folder_path": curr,
                            "asset_stem": stem,
                            "category": c_key,
                            "category_name": c_name,
                            "category_order": c_order,
                            "files": sorted(files),
                            "png_files": sorted(pngs),
                            "atlas_files": sorted(atlases),
                            "skel_files": sorted(skels),
                            "json_files": sorted(jsons),
                            "archive_files": [],
                            "is_multi": True,
                            "texture_count": len(pngs),
                            "has_json_anim": len(jsons) > 0 and len(skels) == 0,
                            "has_backup": spine_merger.has_backup(curr),
                        })
                    else:
                        for e, _ in items:
                            singles.append(e)

                for e in singles:
                    pngs, atlases, skels, jsons, files = _get_spine_assets_in_dir(e.path)
                    stem = _get_asset_stem(skels, jsons, pngs, e.name)
                    c_key, c_name, c_order = _classify_mod_category(e.name, files, False)

                    mods.append({
                        "id": e.name,
                        "name": e.name,
                        "folder_name": e.name,
                        "folder_path": e.path,
                        "asset_stem": stem,
                        "category": c_key,
                        "category_name": c_name,
                        "category_order": c_order,
                        "files": sorted(files),
                        "png_files": sorted(pngs),
                        "atlas_files": sorted(atlases),
                        "skel_files": sorted(skels),
                        "json_files": sorted(jsons),
                        "archive_files": [],
                        "is_multi": False,
                        "texture_count": len(pngs),
                        "has_json_anim": len(jsons) > 0 and len(skels) == 0,
                        "has_backup": spine_merger.has_backup(e.path),
                    })

            for e in non_spine_subdirs:
                if _is_multi_mod_directory(e.path, curr):
                    png_previews = []
                    try:
                        for root, _, files in os.walk(e.path):
                            for f in files:
                                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and not f.startswith("."):
                                    png_previews.append(f)
                                if len(png_previews) >= 10:
                                    break
                            if len(png_previews) >= 10:
                                break
                    except Exception:
                        pass

                    c_key, c_name, c_order = "multi", "Multi Mods", 0
                    mods.append({
                        "id": e.name,
                        "name": e.name,
                        "folder_name": e.name,
                        "folder_path": e.path,
                        "asset_stem": e.name,
                        "category": c_key,
                        "category_name": c_name,
                        "category_order": c_order,
                        "files": [],
                        "png_files": sorted(png_previews),
                        "atlas_files": [],
                        "skel_files": [],
                        "json_files": [],
                        "archive_files": [],
                        "is_multi": True,
                        "texture_count": len(png_previews),
                        "has_json_anim": False,
                        "has_backup": spine_merger.has_backup(e.path),
                    })
                else:
                    _scan_directory(e.path)

        _scan_directory(mods_root)

        for m in mods:
            m["asset_key"] = self.extract_mod_asset_key(m)
            m["asset_keys"] = asset_keys(m.get("files") or [])

        # Sort mods by category order first, then name
        mods.sort(key=lambda m: (m["category_order"], m["name"].lower()))
        if hasattr(self, "scan_cache"):
            with self.scan_cache_lock:
                self.scan_cache[cache_key] = mods
        return mods

    def extract_mod_asset_key(self, mod_info: Dict[str, Any]) -> str:
        """
        Extracts canonical asset key that the mod modifies, e.g.:
          - 'char103701'
          - 'cutscene_char067504'
          - 'illust_dating14'
          - 'specialillust60'
        """
        if not mod_info:
            return "unknown"

        # Explicit key if already present
        k = mod_info.get("asset_key")
        if k and isinstance(k, str) and k != "unknown":
            return k.lower()

        folder_path = mod_info.get("folder_path") or mod_info.get("mod_folder") or ""
        files = mod_info.get("files") or []

        # If files is empty but folder exists on disk, list files directly
        if not files and folder_path and os.path.exists(folder_path) and os.path.isdir(folder_path):
            try:
                files = [f for f in os.listdir(folder_path) if not f.startswith(".")]
            except Exception:
                files = []

        # If repacked_path exists, check mod_meta.json
        prep = mod_info.get("prepared_data") or {}
        r_path = mod_info.get("repacked_path") or prep.get("repacked_path")
        if r_path:
            meta_p = os.path.join(os.path.dirname(r_path), "mod_meta.json")
            if os.path.exists(meta_p):
                try:
                    with open(meta_p, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if meta.get("asset_key"):
                        return meta["asset_key"].lower()
                    if meta.get("asset_stem"):
                        return meta["asset_stem"].lower()
                except Exception:
                    pass

        pattern = r'(cutscene_char\d{4,6}|char\d{4,6}|illust_dating\d+|illust_special\d+|illust_talk\d+|npc\d+|specialillust\w+|storypack\w+)'

        # 1. Search in file names first (highest accuracy for game assets)
        for f in files:
            f_lower = os.path.basename(f).lower()
            m = re.search(pattern, f_lower)
            if m:
                return m.group(1).lower()
            if f_lower.endswith(('.skel', '.json', '.skel.bytes', '.atlas', '.atlas.txt')):
                base = re.sub(r'\.(skel|json|skel\.bytes|atlas|atlas\.txt)$', '', f_lower)
                base = re.sub(r'(_hd|_uhd|_opt)$', '', base)
                m2 = re.search(pattern, base)
                if m2:
                    return m2.group(1).lower()

        # 2. Check asset_stem if present
        stem = (mod_info.get("asset_stem") or prep.get("asset_stem") or "").lower()
        if stem:
            m = re.search(pattern, stem)
            if m:
                return m.group(1).lower()

        # 3. Check mod folder name or mod name
        folder_name = os.path.basename(folder_path or mod_info.get("name", "") or mod_info.get("mod_name", "") or "").lower()
        m = re.search(pattern, folder_name)
        if m:
            return m.group(1).lower()

        # 4. Check full folder path for pattern match (e.g. .../Cutscene/cutscene_char067504)
        if folder_path:
            m_path = re.search(pattern, folder_path.lower())
            if m_path:
                return m_path.group(1).lower()

        raw = stem or folder_name
        cleaned = re.sub(r'(_hd|_uhd|_opt|_\d+)$', '', raw).lower()
        return cleaned or "unknown"

    def get_multi_mod_tree(self, folder_path: str, mod_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspects multi mod folder tree and returns categorized options, previews and variants.
        """
        return multi_manager.inspect_multi_mod_tree(folder_path, mod_name=mod_name)

    def extract_multi_variant(self, variant_path: str, mod_name: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        """
        Inspects a selected variant directory with loose assets.
        Returns (success, message, variant_info).
        """
        if not os.path.exists(variant_path):
            return False, f"Variant folder not found: {variant_path}", {}

        if not os.path.isdir(variant_path):
            return False, f"Variant is not a directory: {variant_path}", {}

        try:
            files = directory_files(variant_path)
        except OSError as exc:
            return False, f"Cannot read variant: {exc}", {}
        if not asset_keys(files):
            return False, "Variant contains no supported Spine assets", {}
        skels = [f for f in files if f.lower().endswith((".skel", ".skel.bytes"))]
        jsons = [f for f in files if f.lower().endswith(".json")]
        pngs = [f for f in files if f.lower().endswith(".png")]
        stem = _get_asset_stem(skels, jsons, pngs, os.path.basename(variant_path))

        return True, "Directory ready", {
            "folder_path": variant_path,
            "files": sorted(files),
            "stem": stem
        }
