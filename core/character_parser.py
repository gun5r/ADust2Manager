import re
import urllib.request
from urllib.parse import urljoin
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional

def format_image_url(costume_id: str) -> str:
    if not costume_id or not re.match(r"^\d+$", costume_id):
        return ""
    return f"https://browndust2.miraheze.org/wiki/Special:FilePath/Illust_inven_char{costume_id}.png"


class _HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: List[List[tuple]] = []
        self.cur_row: List[tuple] = []
        self.cur_cell: List[str] = []
        self.cur_attrs: Dict[str, str] = {}
        # the picture of each cell (cell class -> src), one dict per row in `rows`
        self.row_pictures: List[Dict[str, str]] = []
        self.cur_pictures: Dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self.cur_cell = []
            self.cur_attrs = dict(attrs)
        elif tag == "tr":
            self.cur_row = []
            self.cur_pictures = {}
        elif tag == "img" and self.cur_attrs.get("class"):
            src = dict(attrs).get("src")
            if src:
                self.cur_pictures[self.cur_attrs["class"]] = src

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cur_row.append((self.cur_attrs.get("class", ""), "".join(self.cur_cell).strip()))
        elif tag == "tr":
            if self.cur_row:
                self.rows.append(self.cur_row)
                self.row_pictures.append(self.cur_pictures)

    def handle_data(self, data):
        self.cur_cell.append(data)


def parse_characters_from_html(html_content: str, base_url: str = "") -> List[Dict[str, Any]]:
    """
    Parses character, costume, and asset entries from Brown Dust 2 character tables.
    Categorizes playable heroes, routes multi-name titles to the earliest appearing hero,
    consolidates NPCs into a single 'NPCs' category, and sets up 'Slap Slap Pop' for rhythm minigames.
    Non-playable, non-NPC adventure illustrations (e.g. Kelian, Miracle Twinkle) are omitted so
    they cleanly fall back to 'Others'.
    """
    parser = _HtmlTableParser()
    parser.feed(html_content)

    table_data = []
    cur_char_name = ""
    for r, pictures in zip(parser.rows, parser.row_pictures):
        d = {cls: text for cls, text in r if text}
        if "character-name" in d:
            cur_char_name = d["character-name"]
        cid = d.get("id-cell", "")
        costume = d.get("costume-cell", "")
        if cur_char_name or cid:
            table_data.append({"name": cur_char_name, "id": cid, "costume": costume, "picture": pictures.get("costume-cell", "")})

    # Playable characters have at least one costume starting with char\d+
    playable_chars = {item["name"] for item in table_data if re.match(r"^char\d+", item["id"])}
    sorted_playables = sorted(list(playable_chars), key=lambda x: len(x), reverse=True)

    def find_earliest_playable(text: str) -> Optional[str]:
        matches = []
        text_lower = text.lower()
        for p in sorted_playables:
            pattern = r"(?:\b|_)" + re.escape(p.lower()) + r"(?:\b|_)"
            m = re.search(pattern, text_lower)
            if m:
                matches.append((m.start(), p))
        if matches:
            matches.sort(key=lambda x: x[0])
            return matches[0][1]
        return None

    chars_db: Dict[str, Dict[str, Any]] = {
        p: {"name": p, "costume_ids": [], "aliases": {p.lower(), p.lower().replace(" ", "")}, "costumes": {}, "dating_names": {}}
        for p in sorted_playables
    }
    npc_aliases = {"npc", "npcs"}

    for item in table_data:
        name = item["name"]
        cid = item["id"]
        costume = item["costume"]
        if not name and not cid:
            continue

        if cid == "RhythmHitAnim" or name == "Slap Slap Pop":
            if "Slap Slap Pop" not in chars_db:
                chars_db["Slap Slap Pop"] = {
                    "name": "Slap Slap Pop",
                    "costume_ids": [],
                    "aliases": {"slapslappop", "slap slap pop", "rhythmhitanim"},
                    "costumes": {"RhythmHitAnim": "Slap Slap Pop"},
                    "pictures": {},
                }
            chars_db["Slap Slap Pop"]["aliases"].add("rhythmhitanim")
            if item["picture"]:  # the game has no portrait of its own for it: the website's picture is used
                chars_db["Slap Slap Pop"]["pictures"]["RhythmHitAnim"] = urljoin(base_url, item["picture"])
            continue

        matched_p = find_earliest_playable(name)
        if matched_p:
            entry = chars_db[matched_p]
            if cid:
                if re.match(r"^char\d+", cid):
                    raw_id = cid[4:]
                    if raw_id not in entry["costume_ids"]:
                        entry["costume_ids"].append(raw_id)
                    if costume:
                        entry["costumes"][raw_id] = costume
                elif re.match(r"^illust_dating\d+$", cid, re.I) and costume:
                    # "New Hire / DATING SIM": the scene belongs to the costume of that name
                    entry["dating_names"][cid.lower()] = re.sub(r"\s*/\s*DATING SIM\s*$", "", costume, flags=re.I).strip()
                entry["aliases"].add(cid.lower())
            if name:
                entry["aliases"].add(name.lower())
                entry["aliases"].add(name.lower().replace(" ", ""))
            continue

        is_npc = (
            "npc" in costume.lower()
            or cid.lower().startswith("npc")
            or cid.lower().startswith("illust_talk")
            or "npc" in name.lower()
        )
        if is_npc:
            if name:
                npc_aliases.add(name.lower())
                npc_aliases.add(name.lower().replace(" ", ""))
            if cid:
                npc_aliases.add(cid.lower())
            continue

    chars_db["NPCs"] = {"name": "NPCs", "costume_ids": [], "aliases": npc_aliases, "costumes": {}}

    result = []
    for name, c in sorted(chars_db.items(), key=lambda x: x[0].lower()):
        primary_cid = c["costume_ids"][0] if c["costume_ids"] else next(iter(c.get("pictures", {})), "")
        by_name = {n.lower(): cid for cid, n in c.get("costumes", {}).items()}
        dating = {scene: by_name[n.lower()] for scene, n in c.get("dating_names", {}).items() if n.lower() in by_name}
        result.append({
            "name": c["name"],
            "costume_id": primary_cid,
            "image_url": format_image_url(primary_cid),
            "aliases": sorted(list(c["aliases"])),
            "costumes": c.get("costumes", {}),
            "dating": dating,
            "extra_portraits": c.get("pictures", {}),
        })
    return result


def fetch_and_parse_characters(url: str = "https://browndust2modding.pages.dev/characters") -> List[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ADust2Manager)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_content = resp.read().decode("utf-8", errors="ignore")
    return parse_characters_from_html(html_content, url)

