"""Cache statistics and cleanup for catalogs, originals and repacked bundles."""
import json
import os
import re
import shutil
from mod_assets import _get_asset_stem, asset_keys
from typing import Any, Dict, List


class CacheMixin:
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Calculates storage sizes of original downloaded bundles, catalogs, and repacked files.
        """
        def dir_size(path):
            total = 0
            count = 0
            if os.path.exists(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            total += os.path.getsize(fp)
                            count += 1
                        except OSError:
                            pass
            return total, count

        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

        orig_bytes, orig_files = dir_size(self.originals_dir)
        cat_bytes, cat_files = dir_size(self.cache_dir)
        repack_bytes, repack_files = dir_size(self.repacked_dir)
        thumb_bytes, thumb_files = dir_size(self.thumbs_dir)
        audio_bytes, audio_files = dir_size(self.audio_dir)
        total_bytes = orig_bytes + cat_bytes + repack_bytes + thumb_bytes + audio_bytes

        return {
            "total_bytes": total_bytes,
            "total_formatted": format_size(total_bytes),
            "originals": {
                "bytes": orig_bytes,
                "formatted": format_size(orig_bytes),
                "files": orig_files
            },
            "catalogs": {
                "bytes": cat_bytes,
                "formatted": format_size(cat_bytes),
                "files": cat_files
            },
            "repacked": {
                "bytes": repack_bytes,
                "formatted": format_size(repack_bytes),
                "files": repack_files
            },
            "thumbnails": {
                "bytes": thumb_bytes,
                "formatted": format_size(thumb_bytes),
                "files": thumb_files
            },
            "audio": {
                "bytes": audio_bytes,
                "formatted": format_size(audio_bytes),
                "files": audio_files
            }
        }

    def clear_cache(self, clear_originals: bool = True, clear_repacked: bool = True, clear_catalogs: bool = False, clear_thumbs: bool = False, clear_audio: bool = False) -> Dict[str, Any]:
        """
        Cleans cached original bundles, repacked files, and/or catalogs to free disk space.
        """
        deleted_count = 0
        freed_bytes = 0

        target_dirs = []
        if clear_originals: target_dirs.append(self.originals_dir)
        if clear_repacked: target_dirs.append(self.repacked_dir)
        if clear_catalogs: target_dirs.append(self.cache_dir)
        if clear_thumbs: target_dirs.append(self.thumbs_dir)
        if clear_audio: target_dirs.append(self.audio_dir)

        if clear_catalogs:
            self.cached_indexes.clear()
            with self.catalog_lock:
                self.catalog_cache.clear()

        for d in target_dirs:
            if os.path.exists(d):
                for item in os.listdir(d):
                    item_path = os.path.join(d, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            freed_bytes += os.path.getsize(item_path)
                            os.remove(item_path)
                            deleted_count += 1
                        elif os.path.isdir(item_path):
                            for root, _, files in os.walk(item_path):
                                for f in files:
                                    try:
                                        freed_bytes += os.path.getsize(os.path.join(root, f))
                                    except OSError:
                                        pass
                            shutil.rmtree(item_path)
                            deleted_count += 1
                    except Exception:
                        pass
                os.makedirs(d, exist_ok=True)

        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "freed_formatted": f"{freed_bytes / (1024 * 1024):.1f} MB",
            "updated_stats": self.get_cache_stats()
        }

    def get_cached_repacked_mods(self) -> List[Dict[str, Any]]:
        """
        Scans self.repacked_dir for all repacked/prepared mod bundles.
        Returns a list of dicts with mod_name, bundle_name, bundle_hash, repacked_path,
        size_str, modified_time, etc.
        """
        if not os.path.exists(self.repacked_dir):
            return []

        # Build reverse lookup for hash prefix -> (bundle_name, full_hash) from originals
        hash_to_bundle = {}
        if os.path.exists(self.originals_dir):
            for b_name in os.listdir(self.originals_dir):
                b_path = os.path.join(self.originals_dir, b_name)
                if os.path.isdir(b_path):
                    for b_hash in os.listdir(b_path):
                        if len(b_hash) >= 8:
                            hash_to_bundle[b_hash[:8].lower()] = (b_name, b_hash)
                            hash_to_bundle[b_hash.lower()] = (b_name, b_hash)

        items = []
        for entry in os.listdir(self.repacked_dir):
            if entry.startswith("."):
                continue
            entry_path = os.path.join(self.repacked_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            # Check for __data directly
            data_file = os.path.join(entry_path, "__data")
            nested_b_name = None
            nested_b_hash = None
            if not os.path.exists(data_file):
                subdirs = [d for d in os.listdir(entry_path) if os.path.isdir(os.path.join(entry_path, d))]
                for sub in subdirs:
                    cand = os.path.join(entry_path, sub, "__data")
                    if os.path.exists(cand):
                        data_file = cand
                        nested_b_name = entry
                        nested_b_hash = sub
                        break

            if not os.path.exists(data_file) or os.path.getsize(data_file) == 0:
                # Include corrupted or empty cache folder so the user can see and delete it
                items.append({
                    "id": entry,
                    "folder_name": entry,
                    "mod_name": entry,
                    "bundle_name": "Corrupted",
                    "bundle_hash": "Unknown",
                    "repacked_path": data_file if os.path.exists(data_file) else entry_path,
                    "size_bytes": 0,
                    "size_str": "0 B (Corrupted)",
                    "modified_time": os.path.getmtime(entry_path),
                    "mod_folder": "",
                    "quality": "HD",
                    "is_broken": True,
                    "broken_reason": "Missing or empty __data bundle file"
                })
                continue

            meta_file = os.path.join(os.path.dirname(data_file), "mod_meta.json")
            meta = {}
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass

            size_bytes = os.path.getsize(data_file)
            mtime = os.path.getmtime(data_file)

            mod_name = meta.get("mod_name")
            bundle_name = meta.get("bundle_name")
            bundle_hash = meta.get("bundle_hash")
            mod_folder = meta.get("mod_folder", "")
            quality = meta.get("quality", "HD")

            if not mod_name or not bundle_hash:
                match = re.match(r"^(.+)_([0-9a-fA-F]{8})$", entry)
                if match:
                    mod_name = match.group(1)
                    hash_pfx = match.group(2).lower()
                    if not bundle_name or not bundle_hash:
                        if hash_pfx in hash_to_bundle:
                            bundle_name, bundle_hash = hash_to_bundle[hash_pfx]
                        else:
                            bundle_name = hash_pfx
                            bundle_hash = hash_pfx
                elif nested_b_name and nested_b_hash:
                    bundle_name = nested_b_name
                    bundle_hash = nested_b_hash
                    mod_name = f"Bundle_{bundle_name[:8]}"
                else:
                    mod_name = entry
                    bundle_name = entry
                    bundle_hash = entry

            if size_bytes >= 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024*1024*1024):.1f} GB"
            elif size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024*1024):.1f} MB"
            elif size_bytes >= 1024:
                size_str = f"{size_bytes / 1024:.0f} KB"
            else:
                size_str = f"{size_bytes} B"

            # If asset_stem is equal to mod_name, extract proper spine stem from files or key
            raw_stem = meta.get("asset_stem")
            meta_files = meta.get("files") or []
            if not raw_stem or raw_stem == mod_name or raw_stem == entry:
                skels = [f for f in meta_files if f.lower().endswith(('.skel', '.skel.bytes'))]
                jsons = [f for f in meta_files if f.lower().endswith('.json')]
                pngs = [f for f in meta_files if f.lower().endswith('.png')]
                computed_stem = _get_asset_stem(skels, jsons, pngs, "")
                if computed_stem:
                    raw_stem = computed_stem
                else:
                    ak = meta.get("asset_key") or self.extract_mod_asset_key({
                        "name": mod_name,
                        "folder_path": mod_folder or entry,
                        "files": meta_files
                    })
                    raw_stem = ak if ak and ak != "unknown" else mod_name

            asset_key = meta.get("asset_key")
            if not asset_key or asset_key == "unknown":
                asset_key = self.extract_mod_asset_key({
                    "asset_stem": raw_stem,
                    "name": mod_name,
                    "folder_path": mod_folder or entry,
                    "files": meta_files
                })

            items.append({
                "id": entry,
                "folder_name": entry,
                "mod_name": mod_name,
                "bundle_name": bundle_name,
                "bundle_hash": bundle_hash,
                "repacked_path": data_file,
                "size_bytes": size_bytes,
                "size_str": size_str,
                "modified_time": mtime,
                "mod_folder": mod_folder,
                "mod_folders": meta.get("mod_folders") or [mod_folder],
                "mod_names": meta.get("mod_names") or [mod_name],
                "asset_keys": meta.get("asset_keys") or asset_keys(meta_files),
                "quality": quality,
                "asset_stem": raw_stem,
                "asset_key": asset_key,
                "files": meta_files,
                "is_broken": False
            })

        items.sort(key=lambda x: x["modified_time"], reverse=True)
        return items

    def delete_repacked_mod(self, folder_name: str) -> bool:
        """
        Deletes a repacked mod folder from self.repacked_dir safely.
        """
        safe_name = os.path.basename(folder_name.strip())
        if not safe_name or safe_name in (".", ".."):
            return False
        target = os.path.join(self.repacked_dir, safe_name)
        if os.path.exists(target) and os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
            return True
        return False
