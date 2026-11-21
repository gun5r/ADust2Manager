"""Rebuild the dating-scene data tables from the game itself (see tools/ for the one-shot command line versions).

- dating_rules.json: touch rules, hit sizes and drag destinations of every scene, read from the original dating bundle.
- dating_sound_events.json: FMOD event per touch animation, read from the strings bank inside the game's APK (phone over adb).
- dating_scene_costumes.json: which character costume (= sound bank) each scene uses, found by comparing the animation names
  a scene's spots play with the animations the sound events are named after.
Nothing here is scene-specific: a new dating scene in a game update is picked up by running update_dating_data again.
"""
import json
import os
import re
import subprocess
import tempfile
import warnings
from typing import Callable, Dict, Optional

warnings.filterwarnings("ignore")
import fmod_bank
from paths import GENERATED_DIR

DATA = GENERATED_DIR
RULES_OUT = os.path.join(DATA, "dating_rules.json")
EVENTS_OUT = os.path.join(DATA, "dating_sound_events.json")
COSTUMES_OUT = os.path.join(DATA, "dating_scene_costumes.json")
from game_info import PACKAGE_NAME as PACKAGE, UNITY_VERSION
BUNDLE_IN_APK = "assets/aa/common-soundmaster_assets_all.bundle"
SFX = re.compile(r"^event:/Cinematic/Visual_Novel/Char(\d+)/Interaction/[Ii]dle\d+/(.+)$")
VOICE = re.compile(r"^event:/Voices/Common/Char(\d+)/Interaction/Char\1_Int_(.+)_([A-Z]{2})$")


def anim_key(name: str) -> str:
    """Same normalisation as dating_audio.anim_key (kept here so this module has no circular import)."""
    from dating_audio import anim_key as key
    return key(name)


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def _strings_from_bundle(data: bytes) -> bytes:
    """Master.strings out of the sound-master Unity bundle (a TextAsset)."""
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
    for obj in UnityPy.load(data).objects:  # from memory: a temporary file stays locked by UnityPy on Windows and cannot be deleted
        if obj.type.name == "TextAsset":
            asset = obj.read()
            if asset.m_Name == "Master.strings":
                script = asset.m_Script
                return script.encode("utf-8", "surrogateescape") if isinstance(script, str) else bytes(script)
    raise RuntimeError("The sound bundle holds no Master.strings")


def strings_from_phone(adb_bin: str, device_id: Optional[str] = None) -> bytes:
    """Master.strings (FMOD event paths) out of the game's APK on the phone."""
    base = [adb_bin] + (["-s", device_id] if device_id else [])
    out = subprocess.run(base + ["shell", "pm", "path", PACKAGE], capture_output=True, text=True, timeout=30).stdout.split()
    apks = [p.replace("package:", "") for p in out if p.startswith("package:")]
    if not apks:
        raise RuntimeError("The game is not installed on the connected phone")
    for apk in apks:
        data = subprocess.run(base + ["exec-out", f"unzip -p {apk} {BUNDLE_IN_APK}"], capture_output=True, timeout=300).stdout
        if data:
            return _strings_from_bundle(data)
    raise RuntimeError("Could not read Master.strings from the phone's APK")


def bundle_from_archive(path: str, depth: int = 0) -> Optional[bytes]:
    """The sound-master bundle out of an APK, or an archive of APKs (.xapk, .apks, .zip: the bundle can sit in a split APK)."""
    import io
    import zipfile
    try:
        archive = zipfile.ZipFile(path if depth == 0 else io.BytesIO(path))  # type: ignore[arg-type]
    except (zipfile.BadZipFile, OSError):
        return None
    with archive:
        for name in archive.namelist():
            if name == BUNDLE_IN_APK or re.search(r"(^|/)common-soundmaster_assets_all[^/]*\.bundle$", name):
                return archive.read(name)
        if depth < 2:
            for name in archive.namelist():
                if name.lower().endswith(".apk"):
                    found = bundle_from_archive(archive.read(name), depth + 1)  # type: ignore[arg-type]
                    if found:
                        return found
    return None


def strings_from_apk_file(path: str) -> bytes:
    """Master.strings out of an APK (or xapk/apks/zip of APKs) on this computer, for people without adb."""
    if not os.path.isfile(path):
        raise RuntimeError(f"No file at {path}")
    data = bundle_from_archive(path)
    if data is None:
        raise RuntimeError("That file holds no sound data (assets/aa/common-soundmaster_assets_all.bundle). Use the game's APK; for a split install, the base or assets APK, or the whole .xapk/.apks file.")
    return _strings_from_bundle(data)


def extract_sound_events(strings_blob: bytes, out_path: str = EVENTS_OUT) -> dict:
    table: dict = {}
    for guid, path in fmod_bank.read_strings(strings_blob).items():
        sfx, voice = SFX.match(path), VOICE.match(path)
        if sfx:
            table.setdefault(sfx.group(1), {}).setdefault(anim_key(sfx.group(2)), {}).setdefault("sfx", guid.hex())
        elif voice:
            table.setdefault(voice.group(1), {}).setdefault(anim_key(voice.group(2)), {}).setdefault("voice", {})[voice.group(3)] = guid.hex()
    table = {c: dict(sorted(v.items())) for c, v in sorted(table.items())}
    write_json(out_path, table)
    return table


def match_costumes(rules: dict, events: dict, out_path: str = COSTUMES_OUT) -> Dict[str, str]:
    """scene number -> costume id. Each scene takes the costume whose sound events best overlap the animations its spots play;
    the most certain scenes choose first and a costume is used once (two scenes of one character stay apart)."""
    scored = []
    for scene, data in rules.items():
        used = {anim_key(a) for s in data["spots"] for a in s["anims"] + ([s["stop"]] if s.get("stop") else [])}
        for costume, table in events.items():
            names = {k for k in table if k.startswith("mix")}
            if used and names:
                scored.append((len(used & names) / len(used | names), scene, costume))
    result: Dict[str, str] = {}
    taken: set = set()
    for score, scene, costume in sorted(scored, reverse=True):
        number = scene[len("illust_dating"):]
        if number not in result and costume not in taken and score >= 0.3:
            result[number] = costume
            taken.add(costume)
    write_json(out_path, dict(sorted(result.items(), key=lambda kv: int(kv[0]))))
    return result


def extract_rules(bundle_paths, out_path: str = RULES_OUT) -> dict:
    """Read every dating scene's touch rules from the original dating bundle(s) and write them to out_path. The game keeps all scenes
    in one bundle or (since its November 2026 update) one prefab bundle per scene: each bundle is read on its own (path ids repeat
    between bundles) and the scenes are merged."""
    scenes: dict = {}
    for path in [bundle_paths] if isinstance(bundle_paths, str) else bundle_paths:
        scenes.update(_scenes_in(path))
    scenes = dict(sorted(scenes.items(), key=lambda kv: int(kv[0][len("illust_dating"):])))
    write_json(out_path, scenes)
    return scenes


def _scenes_in(bundle_path: str) -> dict:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
    env = UnityPy.load(bundle_path)
    objs = {o.path_id: o for o in env.objects}
    tt = {}
    def typetree(o):
        if o.path_id not in tt:
            try: tt[o.path_id] = o.read_typetree()
            except Exception: tt[o.path_id] = None
        return tt[o.path_id]
    name, comps, father, tr_go = {}, {}, {}, {}
    for o in env.objects:
        if o.type.name == "GameObject":
            g = typetree(o); name[o.path_id] = g["m_Name"]; comps[o.path_id] = [c["component"]["m_PathID"] for c in g["m_Component"]]
        elif o.type.name in ("RectTransform", "Transform"):
            t = typetree(o); tr_go[o.path_id] = t["m_GameObject"]["m_PathID"]; father[t["m_GameObject"]["m_PathID"]] = t["m_Father"]["m_PathID"]
    def root(g):
        for _ in range(80):
            if not father.get(g): break
            g = tr_go[father[g]]
        return g
    def rect_of(pid):
        """[x, y, w, h] of a RectTransform (or of the one on a component's GameObject), in its parent's local space."""
        o = objs.get(pid)
        if o is None:
            return None
        if o.type.name == "MonoBehaviour":
            owner = typetree(o)["m_GameObject"]["m_PathID"]
            o = next((objs[c] for c in comps.get(owner, []) if objs[c].type.name == "RectTransform"), None)
            if o is None:
                return None
        t = typetree(o)
        if not t or "m_AnchoredPosition" not in t:
            return None
        return [round(t["m_AnchoredPosition"]["x"], 1), round(t["m_AnchoredPosition"]["y"], 1), round(t["m_SizeDelta"]["x"], 1), round(t["m_SizeDelta"]["y"], 1)]

    scenes = {}
    for gid, plist in comps.items():
        r = name[root(gid)]
        m = re.fullmatch(r"(?i)illust_dating(\d+)", r)
        if not m: continue
        scene = scenes.setdefault(f"illust_dating{m.group(1)}", {"groups": [], "spots": []})
        bone, spot, group_data = None, None, None
        for pid in plist:
            o = objs[pid]
            if o.type.name != "MonoBehaviour": continue
            t = typetree(o)
            if not t: continue
            if "boneName" in t: bone = t["boneName"]
            if "_spineInteractionId" in t: spot = t
            if "_defaultSpineMotionByGroup" in t: group_data = t
        if group_data:
            scene["groups"] = [{
                "group": g["InteractionPointGroupId"], "idle": g["GroupDefaultSpineMotionName"], "switch": g["GroupSwitchSpineMotionName"],
                "gauge": {"on": bool(g["_GaugeSettingData"]["IsOn"]), "min": g["_GaugeSettingData"]["MinMaxScore"], "start": g["_GaugeSettingData"]["StartScore"],
                          "decay": g["_GaugeSettingData"]["AutoDecreaseScorePerSecond"], "limit": g["_GaugeSettingData"]["AutoDecreaseScoreMinMaxLimit"],
                          "motions": g["_GaugeSettingData"]["MotionNameByScoreList"]},
                # tools (skins) the player can pick in this phase; spots belong to one tool (0 = the default, bare hand)
                "tools": [{"id": t["ToolId"], "skin": t["SpineSkinName"]} for t in g["InteractionToolGroupDatas"]],
            } for g in group_data["_defaultSpineMotionByGroup"]]
        if spot and bone:
            lp = spot["_longPressSettingData"]
            scene["spots"].append({
                "bone": bone, "phase": spot["_spineInteractionGroupId"], "id": spot["_spineInteractionId"], "tool": spot["spineInteractionToolId"], "kind": "drag" if spot["_interactionActionType"] == 1 else "touch",
                "anims": spot["PlayMixAnimNames"], "random": bool(spot["IsPlayRandomMixAnim"]), "stop": spot["PlayMixAnimNameWhenActionStop"],
                "motion": spot["PlayMotionName"], "next": bool(spot["IsNextStateWhenActionEnd"]), "forceIdle": bool(spot["ForceIdleWhenNextState"]),
                "clickMax": spot["ClickMaxCount"], "clickReset": spot["ContinuousClickResetTime"],
                "longPress": {"type": lp["ActionType"], "threshold": lp["ThresholdTime"], "loop": lp["LoopMixAnimationNames"], "fail": lp["FailMixAnimationNames"], "success": lp["SuccessMixAnimationNames"]},
                "gauge": spot["_gaugeSettingData"], "zone": {"shape": spot["_interactionZoneShape"], "radius": spot["_circleRadiusOfInteractionZone"]},
                # Drags move the spot's own bone (the object is an [Override] bone, IK/transform constraints follow); the action
                # completes when the point reaches the destination rectangle. Rects are in the parent bone's local space.
                "start": rect_of(spot["_rectTransform"]["m_PathID"]), "dest": rect_of(spot["_interactionPointDestination"]["m_PathID"]),
                "area": rect_of(spot["_interactionBoxZoneRectTransform"]["m_PathID"]),
            })
    for s in scenes.values():
        for sp in s["spots"]:  # keep the file small: only fields that carry information
            for key in ("stop", "motion"):
                if not sp[key]: del sp[key]
            if not sp["forceIdle"]: del sp["forceIdle"]
            if not sp["tool"]: del sp["tool"]
            if not sp["gauge"]["IsOn"]: del sp["gauge"]
            if not any(sp["longPress"][k] for k in ("loop", "fail", "success")): del sp["longPress"]
            if sp["kind"] != "drag" or not sp["dest"]: del sp["dest"]
            if sp["kind"] != "drag" or not sp["area"]: del sp["area"]
            sp["size"] = [round(v) for v in (sp["start"] or [0, 0, 0, 0])[2:]]  # touchable area / drag handle
            del sp["start"]
        for g in s["groups"]:
            g["gauge"]["motions"] = [m for m in g["gauge"]["motions"] if m["MixAnimationName"] not in ("", "0")]
        s["groups"].sort(key=lambda g: g["group"]); s["spots"].sort(key=lambda p: (p["phase"], p["id"], p["bone"]))
    return scenes


def update_dating_data(get_strings: Callable[[], bytes], dating_bundle: Callable[[], str], log: Callable[[str], None]) -> dict:
    """Refresh all three tables. `get_strings` returns Master.strings (from the phone or an APK file); `dating_bundle` returns the
    path (or list of paths) of the original dating bundle(s), downloaded on demand."""
    log("Reading the sound event names...")
    events = extract_sound_events(get_strings())
    log(f"Sound events: {len(events)} costumes, {sum(len(v) for v in events.values())} animations.")
    log("Getting the game's dating data (original bundle)...")
    rules = extract_rules(dating_bundle())
    log(f"Touch rules: {len(rules)} scenes, {sum(len(s['spots']) for s in rules.values())} spots.")
    costumes = match_costumes(rules, events)
    log(f"Scene to sound-bank matches: {len(costumes)} of {len(rules)} scenes.")
    return {"scenes": len(rules), "spots": sum(len(s["spots"]) for s in rules.values()), "costumes": len(events), "matched": len(costumes),
            "unmatched": sorted(int(k[len('illust_dating'):]) for k in rules if k[len('illust_dating'):] not in costumes)}
