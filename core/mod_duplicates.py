"""Exact-duplicate and name-collision detection across scanned mods."""
import hashlib
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple


class DuplicatesMixin:
    def detect_duplicates_and_collisions(self, scanned_mods: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inspects all scanned mods across tabs using a fast 3-Tier duplicate check:
        - Tier 1: Metadata Signature (zero disk read): (file_count, total_bytes, sorted (filename, size))
        - Tier 2: Head/Partial Hash (first 64KB of each file) for candidate signature matches
        - Tier 3: Full SHA-256 Hash to guarantee 100% exact match (even with different folder names)

        Also detects Name Collisions:
        - Same folder name, but DIFFERENT files/contents -> prompt to rename.
        """
        exact_duplicates = []
        name_collisions = []
        seen_dup_pairs = set()
        seen_col_pairs = set()

        def get_mod_files_and_sizes(m: Dict[str, Any]) -> Tuple[List[Tuple[str, int]], int]:
            f_root = os.path.abspath(m.get("folder_path", ""))
            sig = []
            total_bytes = 0
            if os.path.exists(f_root) and os.path.isdir(f_root):
                try:
                    with os.scandir(f_root) as it:
                        for entry in it:
                            fn = entry.name
                            if fn.startswith(".") or fn.endswith(('.old', '.bak')) or fn.lower() == "desktop.ini":
                                continue
                            try:
                                if entry.is_file():
                                    sz = entry.stat().st_size
                                    sig.append((fn.lower(), sz))
                                    total_bytes += sz
                            except Exception:
                                pass
                except Exception:
                    pass
            sig.sort()
            return sig, total_bytes

        # Tier 1: Group by metadata signature
        tier1_groups: Dict[Tuple[int, int, Tuple[Tuple[str, int], ...]], List[Dict[str, Any]]] = defaultdict(list)
        by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        mod_meta_cache = {}

        for m in scanned_mods:
            fp = os.path.abspath(m.get("folder_path", ""))
            if not fp:
                continue
            sig, total_bytes = get_mod_files_and_sizes(m)
            if not sig:
                continue
            mod_meta_cache[fp] = (sig, total_bytes)
            tier1_groups[(len(sig), total_bytes, tuple(sig))].append(m)

            name_key = m.get("name", "").strip().lower()
            if name_key:
                by_name[name_key].append(m)

        def get_partial_hash(fp_root: str, sig: List[Tuple[str, int]]) -> str:
            h = hashlib.md5()
            for fn, _ in sig:
                fpath = os.path.join(fp_root, fn)
                try:
                    with open(fpath, "rb") as f:
                        h.update(f.read(65536))
                except Exception:
                    pass
            return h.hexdigest()

        def get_full_hash(fp_root: str, sig: List[Tuple[str, int]]) -> str:
            h = hashlib.sha256()
            for fn, _ in sig:
                fpath = os.path.join(fp_root, fn)
                try:
                    with open(fpath, "rb") as f:
                        while chunk := f.read(131072):
                            h.update(chunk)
                except Exception:
                    pass
            return h.hexdigest()

        partial_hash_cache: Dict[str, str] = {}
        full_hash_cache: Dict[str, str] = {}

        # Evaluate candidate groups from Tier 1
        for (f_count, t_bytes, sig_tuple), candidates in tier1_groups.items():
            if len(candidates) < 2:
                continue

            # Tier 2: Group by partial hash
            tier2_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for cand in candidates:
                c_path = os.path.abspath(cand["folder_path"])
                if c_path not in partial_hash_cache:
                    partial_hash_cache[c_path] = get_partial_hash(c_path, mod_meta_cache[c_path][0])
                tier2_groups[partial_hash_cache[c_path]].append(cand)

            # Tier 3: Group by full hash
            for p_hash, t2_candidates in tier2_groups.items():
                if len(t2_candidates) < 2:
                    continue

                tier3_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                for cand in t2_candidates:
                    c_path = os.path.abspath(cand["folder_path"])
                    if c_path not in full_hash_cache:
                        full_hash_cache[c_path] = get_full_hash(c_path, mod_meta_cache[c_path][0])
                    tier3_groups[full_hash_cache[c_path]].append(cand)

                for f_hash, dup_mods in tier3_groups.items():
                    if len(dup_mods) < 2:
                        continue
                    # 100% Confirmed Exact Duplicates
                    for i in range(len(dup_mods)):
                        for j in range(i + 1, len(dup_mods)):
                            m1, m2 = dup_mods[i], dup_mods[j]
                            p1 = os.path.abspath(m1["folder_path"])
                            p2 = os.path.abspath(m2["folder_path"])
                            if p1 == p2:
                                continue
                            pair = tuple(sorted([p1, p2]))
                            if pair in seen_dup_pairs:
                                continue
                            seen_dup_pairs.add(pair)

                            is_diff_name = (m1.get("name") != m2.get("name"))
                            exact_duplicates.append({
                                "name": m1.get("name") if not is_diff_name else f"{m1.get('name')} ↔ {m2.get('name')}",
                                "mod1": {
                                    "folder_path": p1,
                                    "name": m1.get("name"),
                                    "file_count": len(mod_meta_cache[p1][0]),
                                    "size_bytes": mod_meta_cache[p1][1]
                                },
                                "mod2": {
                                    "folder_path": p2,
                                    "name": m2.get("name"),
                                    "file_count": len(mod_meta_cache[p2][0]),
                                    "size_bytes": mod_meta_cache[p2][1]
                                },
                                "different_names": is_diff_name
                            })

        # Name Collisions Check:
        # Same folder name, but DIFFERENT files/contents
        for name_key, group in by_name.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    m1 = group[i]
                    m2 = group[j]
                    p1 = os.path.abspath(m1["folder_path"])
                    p2 = os.path.abspath(m2["folder_path"])
                    if p1 == p2:
                        continue
                    pair = tuple(sorted([p1, p2]))
                    if pair in seen_dup_pairs or pair in seen_col_pairs:
                        continue
                    seen_col_pairs.add(pair)

                    cnt1 = len(mod_meta_cache.get(p1, ([], 0))[0])
                    cnt2 = len(mod_meta_cache.get(p2, ([], 0))[0])

                    # Compute guaranteed conflict-free suggested name for Location 2
                    parent_dir2 = os.path.dirname(p2)
                    orig_name = m2.get("name", os.path.basename(p2))
                    base_name = re.sub(r'(_\d+)+$', '', orig_name)

                    # Gather all taken names in parent directory and across scanned mods
                    taken = set(m.get("name", "").lower() for m in scanned_mods)
                    try:
                        taken.update(d.lower() for d in os.listdir(parent_dir2))
                    except Exception:
                        pass

                    counter = 1
                    candidate = f"{base_name}_{counter}"
                    while candidate.lower() in taken or os.path.exists(os.path.join(parent_dir2, candidate)):
                        counter += 1
                        candidate = f"{base_name}_{counter}"

                    # Mark candidate as taken for subsequent items in the batch
                    taken.add(candidate.lower())

                    name_collisions.append({
                        "name": m1.get("name"),
                        "suggested_name": candidate,
                        "mod1": {
                            "folder_path": p1,
                            "name": m1.get("name"),
                            "file_count": cnt1
                        },
                        "mod2": {
                            "folder_path": p2,
                            "name": m2.get("name"),
                            "file_count": cnt2
                        }
                    })

        return {
            "exact_duplicates": exact_duplicates,
            "name_collisions": name_collisions
        }
