"""Sounds of the dating scenes for the touch simulator.

The game plays an FMOD event per touch animation (effects: `event:/Cinematic/Visual_Novel/Char<costume>/Interaction/idle<phase>/
mix<p>_<id>_<n>`; some scenes also voice: `.../Char<costume>_Int_<animation>_<LANG>`). An event is a timeline of instruments
(random containers or single clips, with start time, gain, pitch and trigger chance). `generated/dating_sound_events.json`
(animation -> event GUID, built by tools/extract_dating_sounds.py from the game's strings bank) says which event belongs to which
animation; here we download the banks that hold them, read each event's plan (core/fmod_bank.py), decode only the clips it uses
(core/fadpcm.py) and keep plans + WAVs in `work/audio` (separate from the repack caches, so clearing those keeps the audio).
"""
from game_info import UNITY_VERSION
import json
import os
import re
import shutil
import time
import warnings
from typing import Any, Callable, Dict, List, Optional

from paths import GENERATED_DIR

import cdn_downloader
import fadpcm
import fmod_bank

COSTUMES_FILE = os.path.join(GENERATED_DIR, "dating_scene_costumes.json")
_costumes: Optional[Dict[int, str]] = None


_links: Dict[int, str] = {}


def set_scene_links(characters: List[Dict[str, Any]]) -> None:
    """Scene -> costume links of the community website ("New Hire / DATING SIM" = illust_dating1 belongs to costume 003303); a scene the
    Tools table has not matched yet still finds its sound bank through them."""
    _links.clear()
    for character in characters:
        for scene, costume in (character.get("dating") or {}).items():
            number = scene_number(scene)
            if number and costume:
                _links[number] = costume


def scene_costume(number: Optional[int]) -> Optional[str]:
    """Costume id (= sound bank owner) of a scene: the table the Tools menu rebuilds (sound names matched to each skeleton's animations), else the website's link. Nothing is built in."""
    global _costumes
    if _costumes is None:
        try:
            with open(COSTUMES_FILE, encoding="utf-8") as f:
                _costumes = {int(k): v for k, v in json.load(f).items()}
        except (OSError, ValueError):
            _costumes = {}
    return _costumes.get(number) or _links.get(number)


def reload_data() -> None:
    """Forget the cached tables (after the Tools menu rewrote them)."""
    global _costumes, _events, _rules
    _costumes = _events = _rules = None


SFX_BANK = 'visual_interaction_sfx'
# Effects of a scene live in one of these banks (Nebris in the first, Olivier in the second); they are tried in order
# and a later bank is only downloaded when an effect event was not found in the earlier ones.
SFX_BANKS = (SFX_BANK, 'visual_novel_sfx')
MANIFEST_VERSION = 4
SAFE_NAME = re.compile(r'^[A-Za-z0-9_.-]+\.wav$')
EVENTS_FILE = os.path.join(GENERATED_DIR, "dating_sound_events.json")
_events: Optional[Dict[str, Any]] = None


def sound_events(costume: str) -> Dict[str, Any]:
    """animation key -> {'sfx': guid hex, 'voice': {lang: guid hex}} for the costume (empty if unknown)."""
    global _events
    if _events is None:
        try:
            with open(EVENTS_FILE, encoding="utf-8") as f:
                _events = json.load(f)
        except (OSError, ValueError):
            _events = {}
    return _events.get(costume, {})


RULES_FILE = os.path.join(GENERATED_DIR, "dating_rules.json")
_rules: Optional[Dict[str, Any]] = None


def dating_rules_all() -> Dict[str, Any]:
    """Every scene's touch rules (empty without the Tools data)."""
    dating_rules("illust_dating1")  # loads the file
    return _rules or {}


def dating_rules(scene: str) -> Optional[Dict[str, Any]]:
    """The game's touch rules for the scene (idle per phase, spots with their animations and click rules)."""
    global _rules
    if _rules is None:
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                _rules = json.load(f)
        except (OSError, ValueError):
            _rules = {}
    number = scene_number(scene)
    return _rules.get(f"illust_dating{number}") if number else None


def anim_key(name: str) -> str:
    """Spelling-proof key of an animation or event name: `mix1_05_1`, `Mix_1_5_1`, `mix1_5_1` -> `mix1_5_1` (same rule as
    frontend/src/lib/datingAudio.ts animKey)."""
    key = re.sub(r'^(mix|motion|montion)_?', lambda m: 'motion' if m.group(1) != 'mix' else 'mix', name.strip().lower())
    return re.sub(r'\d+', lambda m: str(int(m.group())), key)


def scene_number(scene: str) -> Optional[int]:
    m = re.match(r'(?i)^illust_dating(\d+)', scene or '')
    return int(m.group(1)) if m else None


def clip_file_name(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', name) + '.wav'


class DatingAudioMixin:
    def _scene_dir(self, number: int) -> str:
        return os.path.join(self.audio_dir, f"dating{number}")

    def _read_manifest(self, number: int) -> Optional[Dict[str, Any]]:
        try:
            with open(os.path.join(self._scene_dir(number), "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError):
            return None
        return manifest if manifest.get("version") == MANIFEST_VERSION else None  # older formats are rebuilt

    def dating_audio_status(self, scene: str) -> Dict[str, Any]:
        number = scene_number(scene)
        costume = scene_costume(number)
        events = sound_events(costume) if costume else {}
        if not events:
            return {"available": False, "cached": False}
        manifest = self._read_manifest(number)
        langs = sorted({lang for a in (manifest or {}).get("animations", {}).values() for lang in a.get("voice", {})})
        have_sfx = bool(self._bank_path(SFX_BANK))
        return {"available": True, "cached": manifest is not None, "costume": costume, "voice": langs,
                "animations": len((manifest or {}).get("animations", {})),
                "download_mb": round((0 if have_sfx else 51.0) + (2.0 if any("voice" in e and k.startswith(("mix", "motion")) for k, e in events.items()) else 0), 1)}

    def dating_manifest(self, scene: str) -> Optional[Dict[str, Any]]:
        number = scene_number(scene)
        return self._read_manifest(number) if scene_costume(number) else None

    def dating_clip_path(self, scene: str, name: str) -> Optional[str]:
        number = scene_number(scene)
        if not scene_costume(number) or not SAFE_NAME.match(name):
            return None
        path = os.path.join(self._scene_dir(number), "clips", name)
        return path if os.path.isfile(path) else None

    def _bank_path(self, needle: str) -> Optional[str]:
        banks = os.path.join(self.audio_dir, "_banks")
        if os.path.isdir(banks):
            for f in os.listdir(banks):
                if needle in f:
                    return os.path.join(banks, f)
        return None

    def _fetch_bank(self, needle: str, quality: str, log: Callable[[str], None]) -> str:
        have = self._bank_path(needle)
        if have:
            return have
        version = cdn_downloader.get_cdn_version(quality)
        catalog, err = cdn_downloader.download_catalog(self.cache_dir, quality, version, self.catalog_cache, self.catalog_lock, None)
        if not catalog:
            raise RuntimeError(f"Could not load the game catalog: {err}")
        found = cdn_downloader.find_bundle_by_key(catalog, needle)
        if not found:
            raise RuntimeError(f"The game catalog has no '{needle}' sound bank")
        key, size, bundle_hash = found
        out = os.path.join(self.audio_dir, "_banks", os.path.basename(key).replace(f"_{bundle_hash}", ""))
        log(f"Downloading sound bank {os.path.basename(out)} ({size / 1048576:.1f} MB)...")
        ok, error = cdn_downloader.download_catalog_file(version, quality, key, bundle_hash, size, out)
        if not ok:
            raise RuntimeError(f"Download failed: {error}")
        return out

    @staticmethod
    def _bank_bytes(bundle_path: str) -> bytes:
        import UnityPy
        UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for obj in UnityPy.load(bundle_path).objects:
                if obj.type.name == "TextAsset":
                    script = obj.read().m_Script
                    return script.encode("utf-8", "surrogateescape") if isinstance(script, str) else bytes(script)
        raise RuntimeError("The sound bundle holds no bank")

    def download_dating_audio(self, scene: str, quality: str = "HD", log_cb: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        log = log_cb or (lambda _m: None)
        number = scene_number(scene)
        costume = scene_costume(number)
        events = sound_events(costume) if costume else {}
        if not events:
            raise ValueError(f"No known sounds for '{scene}'")
        scene_dir = self._scene_dir(number)
        os.makedirs(os.path.join(scene_dir, "clips"), exist_ok=True)
        animations: Dict[str, Dict[str, Any]] = {}
        # (bank to read, kind, how to pick the event guids of an animation entry)
        jobs = [(bank, "sfx", lambda e: {"": e["sfx"]} if "sfx" in e else {}) for bank in SFX_BANKS]
        if any("voice" in e and k.startswith(("mix", "motion")) for k, e in events.items()):
            jobs.append((f"interaction_char{costume}", "voice", lambda e: e.get("voice", {})))
        for n, (needle, kind, pick) in enumerate(jobs):
            if kind == "sfx" and n and not any("sfx" in e and "sfx" not in animations.get(k, {}) for k, e in events.items()):
                continue  # every effect was found in an earlier bank
            blob = self._bank_bytes(self._fetch_bank(needle, quality, log))
            samples, data_at, codec = fadpcm.parse_fsb5(blob)
            if codec != fadpcm.CODEC_FADPCM:
                raise RuntimeError(f"Unsupported audio codec {codec} in {needle}")
            bank = fmod_bank.load_bank(blob)
            written: set = set()
            for key, entry in events.items():
                if kind == "voice" and not key.startswith(("mix", "motion")):
                    continue  # expression lines are not tied to a touch animation
                for lang, guid in pick(entry).items():
                    if kind == "sfx" and "sfx" in animations.get(key, {}):
                        continue
                    plan = fmod_bank.event_plan(bank, bytes.fromhex(guid))
                    if not plan:
                        continue
                    for layer in plan:
                        names = []
                        for index in layer["clips"]:
                            name = f"{kind}{n or ''}_{index}.wav"
                            if index not in written:
                                with open(os.path.join(scene_dir, "clips", name), "wb") as f:
                                    f.write(fadpcm.sample_to_wav(blob, data_at, samples[index]))
                                written.add(index)
                            names.append(name)
                        layer["clips"] = names
                    slot = animations.setdefault(key, {})
                    if kind == "sfx":
                        slot["sfx"] = plan
                    else:
                        slot.setdefault("voice", {})[lang] = plan
            log(f"Decoded {len(written)} {kind} clips.")
        manifest = {"version": MANIFEST_VERSION, "scene": f"illust_dating{number}", "costume": costume, "animations": animations, "downloaded_at": time.time()}
        with open(os.path.join(scene_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, separators=(",", ":"))
        return self.dating_audio_status(scene)

    def tool_icon_path(self, number: int, quality: str = "HD", log_cb: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """File of icon_interaction_toolbar_<number>.png (tool id + 1), cut from the game's atlas on first use (0.2 MB download)."""
        if not 1 <= number <= 30:
            return None
        icons = os.path.join(self.work_dir, "tool_icons")
        path = os.path.join(icons, f"icon_interaction_toolbar_{number}.png")
        if not os.path.isfile(path):
            from tool_icons import extract_tool_icons
            bundle = self._fetch_bank("interactiongui.spriteatlasv2", quality, log_cb or (lambda _m: None))
            extract_tool_icons(bundle, icons)
        return path if os.path.isfile(path) else None

    def clear_audio_cache(self) -> int:
        """Delete every downloaded bank and decoded clip; returns the bytes freed."""
        freed = 0
        for root, _dirs, files in os.walk(self.audio_dir):
            for name in files:
                try:
                    freed += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        shutil.rmtree(self.audio_dir, ignore_errors=True)
        os.makedirs(self.audio_dir, exist_ok=True)
        return freed
