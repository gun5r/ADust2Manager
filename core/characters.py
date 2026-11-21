import os
import json
import re
from typing import List, Dict, Any, Optional
try:
    from core.character_parser import format_image_url, fetch_and_parse_characters
except ImportError:
    from character_parser import format_image_url, fetch_and_parse_characters

class CharacterManager:
    def __init__(self, base_dir: str, db=None):
        self.base_dir = base_dir
        self.db = db
        self.chars_file = os.path.join(base_dir, "characters.json")
        self.characters = self.load_characters()

    def load_characters(self) -> List[Dict[str, Any]]:
        if self.db is not None or os.path.exists(self.chars_file):
            try:
                if self.db is not None:
                    data = self.db.load_characters()
                else:
                    with open(self.chars_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
                if self.cleared():
                    return []
            except Exception as e:
                print(f"[CharacterManager] Error loading {self.chars_file}: {e}")

        return []  # nothing is built in: Tools > Update Characters (or Initial Setup) builds the list from the website

    CLEARED = "characters_cleared"

    def cleared(self) -> bool:
        """True after "delete all character data": nothing is re-seeded until the next update from the website."""
        return bool(self.db is not None and self.db.get_meta(self.CLEARED))

    def clear_characters(self):
        if self.db is not None:
            self.db.set_meta(self.CLEARED, "1")
        self.save_characters([])

    def save_characters(self, characters: List[Dict[str, Any]]):
        try:
            if self.db is not None:
                self.db.save_characters(characters)
            else:
                with open(self.chars_file, "w", encoding="utf-8") as f:
                    json.dump(characters, f, indent=2, ensure_ascii=False)
            self.characters = characters
        except Exception as e:
            print(f"[CharacterManager] Error saving {self.chars_file}: {e}")

    def add_or_update_character(self, name: str, costume_id: str = "", image_url: str = "") -> Dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("Character name cannot be empty")

        if not image_url and costume_id:
            image_url = format_image_url(costume_id)

        existing = next((c for c in self.characters if c["name"].lower() == name.lower()), None)
        if existing:
            if costume_id:
                existing["costume_id"] = costume_id
            if image_url:
                existing["image_url"] = image_url
            entry = existing
        else:
            entry = {
                "name": name,
                "costume_id": costume_id,
                "image_url": image_url or (format_image_url(costume_id) if costume_id else ""),
                "aliases": [name.lower(), name.lower().replace(" ", "")],
                "costumes": {},
            }
            self.characters.append(entry)

        self.characters.sort(key=lambda x: x["name"].lower())
        self.save_characters(self.characters)
        return entry

    def sync_from_web(self, url: str = "https://browndust2modding.pages.dev/characters") -> Dict[str, Any]:
        try:
            fresh_chars = fetch_and_parse_characters(url)
        except Exception as e:
            raise RuntimeError(f"Could not reach community database: {e}. Existing character database preserved.")

        fresh_map = {c["name"].lower(): c for c in fresh_chars}

        added_count = 0
        updated_count = 0

        # Preserve ALL custom user-added characters not in web database
        custom_chars = [
            c for c in self.characters
            if c["name"].lower() not in fresh_map
        ]

        merged_list = []
        for fresh in fresh_chars:
            name_low = fresh["name"].lower()
            existing = next((c for c in self.characters if c["name"].lower() == name_low), None)
            if existing:
                all_aliases = sorted(list(set(existing.get("aliases", []) + fresh.get("aliases", []))))
                fresh["aliases"] = all_aliases
                if existing.get("image_url") and not fresh.get("image_url"):
                    fresh["image_url"] = existing["image_url"]
                updated_count += 1  # the website is the truth for names, costumes and dating links
            else:
                added_count += 1
            merged_list.append(fresh)

        merged_list.extend(custom_chars)
        merged_list.sort(key=lambda x: x["name"].lower())
        if self.db is not None:
            self.db.set_meta(self.CLEARED, "")
        self.save_characters(merged_list)

        return {"added": added_count, "updated": updated_count, "total": len(self.characters)}

    # One character per asset: dating illustrations and costumes. Story assets (specialillust, npc, illust_special)
    # are shared by several characters, so they only break ties when the title names nobody.
    OWNED_ASSET = r"illust_dating\d+|char\d{4,6}"
    SHARED_ASSET = r"illust_special\d+|specialillust\d+|npc\d+"

    def match_by_asset(self, files: List[str], pattern: str = OWNED_ASSET) -> Optional[str]:
        """Character owning the game asset a mod replaces (file names / asset key)."""
        for asset in re.findall(f"({pattern})", " ".join(files).lower()):
            linked = next((c["name"] for c in self.characters if asset in (c.get("dating") or {})), None)
            if linked:
                return linked
            for char in self.characters:
                if asset in (a.lower() for a in char.get("aliases") or []):
                    return char["name"]
            if asset.startswith("char") and len(asset) >= 8:
                cid = asset[4:]
                for char in self.characters:
                    if cid == (char.get("costume_id") or ""):
                        return char["name"]
        return None

    def match_character(self, mod_name: str, files: Optional[List[str]] = None) -> Optional[str]:
        # The asset a mod replaces decides; the mod's title is only a fallback (a title like
        # "Tyr_..._Dating_1" must not be read as the asset illust_dating1).
        by_asset = self.match_by_asset(files or [])
        if by_asset:
            return by_asset

        target_texts = [mod_name]
        if files:
            target_texts.extend(files[:15])

        raw_combined = " ".join(target_texts).lower()

        clean_mod_name = re.sub(r"[_.\-\s]+", " ", mod_name).lower()
        sorted_chars = sorted(self.characters, key=lambda c: len(c["name"]), reverse=True)

        # 1. Earliest-appearing character name in mod name (handles multi-character titles)
        earliest_match = None
        earliest_pos = float("inf")
        for char in sorted_chars:
            if char["name"] == "NPCs":
                continue
            cname = char["name"].lower()
            pattern = r"(?:\b|_)" + re.escape(cname) + r"(?:\b|_)"
            m = re.search(pattern, clean_mod_name)
            if m and m.start() < earliest_pos:
                earliest_pos = m.start()
                earliest_match = char["name"]

        if earliest_match:
            return earliest_match

        by_story_asset = self.match_by_asset(files or [], self.SHARED_ASSET)
        if by_story_asset:
            return by_story_asset

        # 2. Check aliases against mod name and file hints
        clean_texts = [re.sub(r"[_.\-\s]+", " ", t).lower() for t in target_texts]
        for char in sorted_chars:
            aliases = char.get("aliases") or []
            for alias in aliases:
                a_clean = alias.lower()
                pattern = r"(?:\b|_)" + re.escape(a_clean) + r"(?:\b|_)"
                for t in clean_texts:
                    if re.search(pattern, t) or a_clean.replace(" ", "") in t.replace(" ", ""):
                        return char["name"]

        # 3. Costume ID matches (char\d{4,6})
        found_cids = re.findall(r"char(\d{4,6})", raw_combined)
        for cid in found_cids:
            for char in sorted_chars:
                c_costume = char.get("costume_id") or ""
                if cid == c_costume or (len(cid) >= 4 and c_costume.startswith(cid[:4])):
                    return char["name"]
                if any(a.endswith(cid) for a in char.get("aliases", [])):
                    return char["name"]

        return None
