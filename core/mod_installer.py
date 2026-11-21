"""Resolve, fetch, repack, prepare and install mods."""
from game_info import UNITY_VERSION
import cdn_downloader
import json
import os
import re
import resolver
import tempfile
import threading
from prepare_gate import Cancelled
from mod_assets import asset_keys, directory_files, source_fingerprint
from pathlib import Path
from persistence import write_json_atomic
from repacker.repacker import repack_bundle
from typing import Any, Dict, List, Optional, Tuple


class InstallerMixin:
    def get_or_load_index(self, quality: str = "HD", log_cb = None) -> Optional[Dict[str, Any]]:
        """
        Loads or builds the catalog index needed to map mod file names to bundle hashes.
        """
        import catalog_indexer

        # 1. Fetch latest CDN version
        if log_cb: log_cb("Fetching latest game CDN catalog...")
        version = cdn_downloader.get_cdn_version(quality)
        if not version:
            if log_cb: log_cb("Failed to reach CDN version endpoint.")
            return None

        cache_key = (quality, version)
        if cache_key in self.cached_indexes:
            return self.cached_indexes[cache_key]
        with self.index_lock:
            if cache_key in self.cached_indexes:
                return self.cached_indexes[cache_key]

            # 2. Check if pre-built asset index exists on disk
            index_file = os.path.join(self.cache_dir, f"asset_index_{quality.lower()}_{version}.json")
            if os.path.exists(index_file):
                try:
                    if log_cb: log_cb(f"Loading cached asset index ({quality}_{version})...")
                    with open(index_file, "r", encoding="utf-8") as f:
                        self.cached_indexes[cache_key] = json.load(f)
                    return self.cached_indexes[cache_key]
                except Exception as e:
                    if log_cb: log_cb(f"Notice reading cached index: {e}")

            # 4. Download catalog from CDN
            if log_cb: log_cb(f"Downloading CDN catalog for version {version}...")
            catalog_content, err = cdn_downloader.download_catalog(
                self.cache_dir, quality, version, self.catalog_cache, self.catalog_lock, log_cb
            )
            if err or not catalog_content:
                if log_cb: log_cb(f"Error downloading catalog: {err}")
                return None

            # 5. Build index from catalog
            if log_cb: log_cb("Building asset-to-bundle lookup map from catalog...")
            try:
                index_data = catalog_indexer.load_or_build_asset_index(
                    self.cache_dir, quality, version, catalog_content
                )
                self.cached_indexes[cache_key] = index_data
                if log_cb: log_cb("Asset index ready.")
                return index_data
            except Exception as e:
                if log_cb: log_cb(f"Catalog indexer error: {e}")
                return None

    def resolve_mod(self, mod_info: Dict[str, Any], quality: str = "HD", log_cb = None) -> Dict[str, Any]:
        """
        Resolves which Unity asset bundle this mod belongs to.
        """
        index = self.get_or_load_index(quality, log_cb)
        file_names = mod_info.get("files", [])
        
        # Use resolver
        res = resolver.resolve_mod_folder(file_names, index or {})
        return res

    def fetch_bundle(
        self, 
        bundle_name: str, 
        quality: str = "HD", 
        device_id: Optional[str] = None, 
        log_cb = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Fetches the original bundle either from CDN or connected phone. Mods that share a bundle wait for one download instead of
        each starting their own.
        """
        with self._bundle_locks_guard:
            lock = self._bundle_locks.setdefault(bundle_name, threading.Lock())
        with lock:
            return self._fetch_bundle(bundle_name, quality, device_id, log_cb)

    def _fetch_bundle(
        self,
        bundle_name: str,
        quality: str,
        device_id: Optional[str],
        log_cb,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # First check CDN catalog for bundle info
        version = cdn_downloader.get_cdn_version(quality)
        catalog_content, _ = cdn_downloader.download_catalog(
            self.cache_dir, quality, version, self.catalog_cache, self.catalog_lock, None
        )

        bundle_hash = None
        if catalog_content:
            # Look up bundle_hash in catalog
            try:
                # Search bundle hash in catalog_content
                # cdn_downloader.find_and_download_bundle handles searching and downloading
                if log_cb: log_cb(f"Downloading original bundle '{bundle_name}' from Neowiz CDN...")
                dest_path, err = cdn_downloader.find_and_download_bundle(
                    catalog_content=catalog_content,
                    version=version,
                    quality=quality,
                    hashed_name=bundle_name,
                    output_dir=self.originals_dir,
                    progress_callback=log_cb
                )
                if dest_path and os.path.exists(dest_path):
                    # extract hash from path: originals_dir/<bundle_name>/<bundle_hash>/__data
                    parts = Path(dest_path).parts
                    b_hash = parts[-2]
                    b_name = parts[-3]
                    return dest_path, b_name, b_hash
                elif err and log_cb:
                    log_cb(f"CDN download notice: {err}")
            except Exception as ex:
                if log_cb: log_cb(f"CDN error: {ex}")

        # Fallback: Pull from connected ADB phone
        if device_id:
            if log_cb: log_cb(f"Attempting to pull bundle '{bundle_name}' from phone via ADB...")
            bundles = self.adb.list_cached_bundles(device_id)
            match = next((b for b in bundles if b["name"] == bundle_name), None)
            if match:
                b_hash = match["hash"]
                local_dest = os.path.join(self.originals_dir, bundle_name, b_hash, "__data")
                success, msg = self.adb.pull_bundle(device_id, bundle_name, b_hash, local_dest)
                if success:
                    return local_dest, bundle_name, b_hash
                elif log_cb:
                    log_cb(f"ADB pull failed: {msg}")

        return None, None, None

    def original_bundle_for(self, mod_folder: str, quality: str = "HD", log_cb=None) -> Tuple[Optional[str], List[str], str]:
        """The original game bundle a mod replaces, downloaded when needed: (path, asset keys, "") or (None, [], reason)."""
        files = directory_files(mod_folder)
        keys = asset_keys(files)
        if not keys:
            return None, [], "The folder names no game asset to look up"
        result = self.resolve_mod({"folder_path": mod_folder, "files": files}, quality, log_cb)
        bundle = result.get("targetHash")
        if not bundle:
            return None, [], "Could not find the game bundle this mod replaces"
        with self.download_gate.slot(None):
            path, _, _ = self.fetch_bundle(bundle, quality, None, log_cb)
        if not path:
            return None, [], f"Could not download the original bundle '{bundle}'"
        return path, keys, ""

    def original_skeleton(self, mod_folder: str, quality: str = "HD", log_cb=None) -> Tuple[Optional[bytes], str]:
        """The game's own skeleton for the asset a mod replaces, read from the original bundle: (bytes, "") or (None, reason)."""
        import UnityPy
        path, keys, reason = self.original_bundle_for(mod_folder, quality, log_cb)
        if not path:
            return None, reason
        UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
        wanted = {k.lower() for k in keys}
        for obj in UnityPy.load(path).objects:
            if obj.type.name not in ("TextAsset", "MonoBehaviour"):
                continue
            data = obj.read()
            name = (getattr(data, "m_Name", "") or "").lower()
            if ".skel" not in name or re.sub(r"\.skel(\.bytes)?$", "", name) not in wanted:
                continue
            content = data.m_Script
            return (content.encode("utf-8", "surrogateescape") if isinstance(content, str) else bytes(content)), ""
        return None, "The original bundle has no skeleton for this asset"

    def repack_mod(
        self,
        mod_folder: str,
        original_bundle_path: str,
        bundle_name: str,
        bundle_hash: str,
        log_cb = None
    ) -> Tuple[bool, str, str]:
        """
        Repacks modded assets into original bundle.
        Returns: (success, repacked_bundle_path, message)
        """
        output_data_path = os.path.join(self.repacked_dir, bundle_name, bundle_hash, "__data")
        os.makedirs(os.path.dirname(output_data_path), exist_ok=True)

        if log_cb: log_cb(f"Starting repack for {os.path.basename(mod_folder)}...")
        
        success, msg = repack_bundle(
            original_bundle_path=original_bundle_path,
            modded_assets_folder=mod_folder,
            output_path=output_data_path,
            use_astc=True,
            progress_callback=log_cb
        )

        return success, output_data_path, msg

    def install_mod_to_phone(
        self,
        mod_folder: str,
        device_id: str,
        quality: str = "HD",
        log_cb = None
    ) -> Tuple[bool, str]:
        """
        End-to-end mod installation:
        1. Resolve mod
        2. Fetch original bundle
        3. Repack on PC
        4. Push to phone via ADB
        """
        if log_cb: log_cb(f"=== Processing Mod: {os.path.basename(mod_folder)} ===")

        # Ensure all filenames and atlas references are strictly lowercase
        self.sanitize_mod_filenames(mod_folder, log_cb)

        # 1. Resolve
        scan_results = self.scan_mods_folder(os.path.dirname(mod_folder))
        mod_info = next((m for m in scan_results if m["folder_path"] == mod_folder), None)
        if not mod_info:
            # Create a single mod info
            files = [f for f in os.listdir(mod_folder) if not f.startswith(".")]
            mod_info = {"id": os.path.basename(mod_folder), "files": files, "folder_path": mod_folder}

        res = self.resolve_mod(mod_info, quality, log_cb)
        target_bundle = res.get("targetHash")
        if not target_bundle:
            return False, f"Could not resolve target bundle for {mod_folder}. Unresolved: {res.get('unresolvedFiles')}"

        if log_cb: log_cb(f"Resolved target bundle: {target_bundle}")

        # 2. Fetch bundle
        orig_path, b_name, b_hash = self.fetch_bundle(target_bundle, quality, device_id, log_cb)
        if not orig_path or not b_hash:
            return False, f"Failed to acquire original bundle '{target_bundle}' from CDN or Phone."

        # 3. Repack
        success, repacked_path, msg = self.repack_mod(mod_folder, orig_path, b_name, b_hash, log_cb)
        if not success:
            return False, f"Repack failed: {msg}"

        # 4. Push to phone
        push_ok, push_msg = self.adb.push_modded_bundle(
            device_id=device_id,
            local_data_path=repacked_path,
            bundle_name=b_name,
            bundle_hash=b_hash,
            backup_original=True,
            progress_callback=log_cb
        )

        if push_ok:
            if log_cb: log_cb("🎉 Mod successfully installed and active on phone!")
            return True, f"Mod installed successfully ({b_name})"
        else:
            return False, f"ADB push failed: {push_msg}"

    def prepare_mod(
        self,
        mod_folder: Any,
        quality: str = "HD",
        log_cb = None,
        is_cancelled = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Prepares mod(s) locally on PC:
        Supports single mod folder (str) or multiple mod folders (list of str) for shared bundle merging.
        1. Sanitizes filenames to lowercase
        2. Resolves target bundle
        3. Downloads/fetches original bundle from CDN or local cache
        4. Repacks with ASTC compression into isolated local folder
        Returns (success, prep_dict, error_msg)
        """
        requested = mod_folder if isinstance(mod_folder, list) else [mod_folder]
        if not requested or any(not isinstance(f, str) or not f or not os.path.isdir(f) for f in requested):
            return False, None, "All mod sources must be existing directories"
        folder_list = list(dict.fromkeys(os.path.abspath(f) for f in requested))
        primary_folder = folder_list[0]
        mod_folders_to_repack = folder_list if len(folder_list) > 1 else primary_folder
        mod_names = [os.path.basename(f) for f in folder_list]
        mod_dir_name = mod_names[0] if len(mod_names) == 1 else f"{mod_names[0]}_merged_{len(mod_names)}mods"

        if is_cancelled and is_cancelled():
            if log_cb: log_cb(f"Preparation cancelled for: {mod_dir_name}")
            return False, None, "Cancelled by user"

        if log_cb: 
            if len(folder_list) > 1:
                log_cb(f"=== Preparing Shared Bundle Merged Mods ({len(folder_list)} mods): {', '.join(mod_names)} ===")
            else:
                log_cb(f"=== Preparing Mod: {mod_dir_name} ===")

        # Ensure lowercase across all folders
        for fld in folder_list:
            ok, error = self.sanitize_mod_filenames(fld, log_cb)
            if not ok:
                return False, None, error

        if is_cancelled and is_cancelled():
            if log_cb: log_cb(f"Preparation cancelled for: {mod_dir_name}")
            return False, None, "Cancelled by user"

        # Resolve every source; unrelated bundles must be prepared separately.
        mod_infos = []
        seen_keys = set()
        target_bundle = None
        for folder in folder_list:
            files = directory_files(folder)
            keys = asset_keys(files)
            overlaps = seen_keys.intersection(keys)
            if overlaps:
                return False, None, f"Conflicting replacement assets: {', '.join(sorted(overlaps))}"
            seen_keys.update(keys)
            info = {"folder_path": folder, "files": files, "asset_stem": keys[0] if keys else os.path.basename(folder)}
            result = self.resolve_mod(info, quality, log_cb)
            resolved = result.get("targetHash")
            if not resolved:
                return False, None, f"Could not resolve target bundle for {os.path.basename(folder)}"
            if target_bundle and resolved != target_bundle:
                return False, None, "Selected mods target different bundles; prepare them separately"
            target_bundle = resolved
            mod_infos.append(info)
        mod_info = mod_infos[0]
        try:
            fingerprint = source_fingerprint(folder_list)
        except OSError as exc:
            return False, None, f"Cannot read mod source: {exc}"

        if log_cb: log_cb(f"Resolved target bundle: {target_bundle}")

        if is_cancelled and is_cancelled():
            if log_cb: log_cb(f"Preparation cancelled for: {mod_dir_name}")
            return False, None, "Cancelled by user"

        # 2. Fetch bundle (from CDN or local originals)
        try:
            with self.download_gate.slot(is_cancelled):
                orig_path, b_name, b_hash = self.fetch_bundle(target_bundle, quality, None, log_cb)
        except Cancelled:
            return False, None, "Cancelled by user"
        if not orig_path or not b_hash:
            return False, None, f"Failed to acquire original bundle '{target_bundle}' from CDN or cache."

        if is_cancelled and is_cancelled():
            if log_cb: log_cb(f"Preparation cancelled for: {mod_dir_name}")
            return False, None, "Cancelled by user"

        # 3. Check pre-bundle cache for instant recall
        output_data_path = os.path.join(self.repacked_dir, f"{mod_dir_name[:80]}_{quality}_{b_hash[:8]}_{fingerprint[:16]}", "__data")
        meta_path = os.path.join(os.path.dirname(output_data_path), "mod_meta.json")
        if os.path.exists(output_data_path) and os.path.getsize(output_data_path) > 0 and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                if cached_data.get("quality") == quality and cached_data.get("source_fingerprint") == fingerprint:
                    if log_cb: log_cb(f"Reusing cached preparation for {mod_dir_name} [{quality}] (ready to bundle & transfer).")
                    return True, cached_data, "Prepared from cache"
            except Exception:
                pass

        if log_cb: log_cb(f"Starting repack for {mod_dir_name} [{quality}]...")
        # Repacking (UnityPy + multi-threaded ASTC) is what loads the PC, so one mod works at a time unless Turbo Mode is on.
        wait_note = lambda: log_cb and log_cb(f"Waiting for the mod being repacked to finish before {mod_dir_name} (Turbo Mode is off)...")
        try:
            with self.work_gate.slot(is_cancelled, wait_note):
                # Publish completed output atomically; failed or concurrent writes stay isolated. The final folder is only
                # created at publish time so nothing half-made ever shows up in the cache list.
                with tempfile.TemporaryDirectory(prefix=".prepare_", dir=self.repacked_dir) as staging:
                    staged_output = os.path.join(staging, "__data")
                    success, msg = repack_bundle(
                        original_bundle_path=orig_path,
                        modded_assets_folder=mod_folders_to_repack,
                        output_path=staged_output,
                        use_astc=True,
                        progress_callback=log_cb,
                        is_cancelled=is_cancelled,
                        quality=quality
                    )
                    if not success:
                        return False, None, "Cancelled by user" if "cancelled" in msg.lower() else f"Repack failed: {msg}"
                    if is_cancelled and is_cancelled():
                        return False, None, "Cancelled by user"
                    if not os.path.isfile(staged_output) or not os.path.getsize(staged_output):
                        return False, None, "Repacker produced no bundle data"
                    os.makedirs(os.path.dirname(output_data_path), exist_ok=True)
                    os.replace(staged_output, output_data_path)
        except Cancelled:
            return False, None, "Cancelled by user"

        prep_data = {
            "source_fingerprint": fingerprint,
            "asset_keys": sorted(seen_keys),
            "mod_folder": primary_folder,
            "mod_folders": folder_list,
            "mod_name": mod_dir_name,
            "mod_names": mod_names,
            "bundle_name": b_name,
            "bundle_hash": b_hash,
            "repacked_path": output_data_path,
            "quality": quality,
            "asset_stem": mod_info.get("asset_stem") if (mod_info.get("asset_stem") and mod_info.get("asset_stem") != mod_dir_name) else (self.extract_mod_asset_key(mod_info) if self.extract_mod_asset_key(mod_info) != "unknown" else mod_dir_name),
            "asset_key": self.extract_mod_asset_key(mod_info),
            "files": sorted({f for info in mod_infos for f in info["files"]})
        }
        # Save metadata for instant cache recall
        try:
            meta_path = os.path.join(os.path.dirname(output_data_path), "mod_meta.json")
            write_json_atomic(meta_path, prep_data)
        except OSError as exc:
            if log_cb: log_cb(f"Prepared bundle, but could not save cache metadata: {exc}")

        return True, prep_data, "Prepared successfully"

    def check_shared_bundles(
        self,
        new_mod_folders: List[str],
        candidate_mods: List[Dict[str, Any]],
        quality: str = "HD",
        log_cb = None,
        lookup = None
    ) -> Dict[str, Any]:
        """
        `lookup(folder_path)` may return a mod's already-known record (the index), which avoids scanning its whole parent
        folder from disk.

        Given a list of new mod folders to prepare, identifies which candidate mods
        (such as currently installed mods that aren't in new_mod_folders) share the exact
        same target bundle hash.
        
        Only mods modifying DIFFERENT asset keys (e.g. illust_dating3 vs illust_dating16,
        or cutscene_char067103 vs cutscene_char003101) are candidates for bundling together.
        Mods modifying the exact same asset key (e.g. cutscene_char003101 and cutscene_char003101)
        are direct conflicting replacements and MUST NOT be bundled together.
        """
        new_norm = {os.path.abspath(f): f for f in new_mod_folders if f}
        target_hashes_for_new = {}
        by_hash_new = {}

        for n_path in new_norm:
            info = lookup(n_path) if lookup else None
            if not info:
                scanned = self.scan_mods_folder(os.path.dirname(n_path))
                info = next((m for m in scanned if os.path.abspath(m["folder_path"]) == n_path), None)
            if not info:
                files = [f for f in os.listdir(n_path) if not f.startswith(".")] if os.path.exists(n_path) else []
                info = {"id": os.path.basename(n_path), "name": os.path.basename(n_path), "files": files, "folder_path": n_path}
            res = self.resolve_mod(info, quality, log_cb)
            t_hash = res.get("targetHash")
            if t_hash:
                target_hashes_for_new[n_path] = t_hash
                by_hash_new.setdefault(t_hash, []).append(info)

        shared_mods = []
        for cand in candidate_mods:
            c_path = os.path.abspath(cand.get("folder_path", ""))
            if c_path in new_norm:
                continue
            c_res = self.resolve_mod(cand, quality, log_cb)
            c_target = c_res.get("targetHash")
            if c_target and c_target in target_hashes_for_new.values():
                shared_mods.append({
                    "name": cand.get("name", os.path.basename(c_path)),
                    "folder_path": c_path,
                    "character": cand.get("character", "Others"),
                    "category": cand.get("category", "other"),
                    "target_hash": c_target,
                    "files": cand.get("files", []),
                    "asset_stem": cand.get("asset_stem", ""),
                    "source": cand.get("source", "installed")
                })

        all_target_hashes = set(target_hashes_for_new.values())
        bundle_groups = {}
        for b_hash in all_target_hashes:
            new_mods_in_bundle = by_hash_new.get(b_hash, [])
            new_asset_keys = {self.extract_mod_asset_key(m) for m in new_mods_in_bundle}

            # Only candidate mods that modify a DIFFERENT asset key/mod type can be bundled together!
            # If a candidate mod modifies the SAME asset key as any new mod, they are direct conflicting
            # replacements and MUST NOT be suggested for bundling!
            cand_items = [
                m for m in shared_mods 
                if m.get("target_hash") == b_hash and self.extract_mod_asset_key(m) not in new_asset_keys
            ]

            new_items = [{
                "name": m.get("name", os.path.basename(m["folder_path"])),
                "folder_path": m["folder_path"],
                "character": m.get("character", "Others"),
                "category": m.get("category", "other"),
                "asset_key": self.extract_mod_asset_key(m),
                "source": "new"
            } for m in new_mods_in_bundle]

            unique_new_keys = set(m["asset_key"] for m in new_items)
            # Only suggest bundling if there is genuinely more than 1 distinct mod asset to bundle together!
            if (len(new_items) > 0 and len(cand_items) > 0) or (len(new_items) > 1 and len(unique_new_keys) > 1):
                bundle_groups[b_hash] = {
                    "bundle_hash": b_hash,
                    "new_mods": new_items,
                    "queue_mods": [m for m in cand_items if m.get("source") == "queue"],
                    "installed_mods": [m for m in cand_items if m.get("source") == "installed"],
                    "total_mods_count": len(new_items) + len(cand_items)
                }

        return {
            "has_shared": len(bundle_groups) > 0,
            "bundle_groups": bundle_groups,
            "shared_mods": shared_mods,
            "target_hashes": list(all_target_hashes)
        }
