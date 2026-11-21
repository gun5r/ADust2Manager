import os
from game_info import UNITY_VERSION
from paths import helper_command
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web.state import character_manager, configured_quality, emit_log, load_config, manager, track
from web.routers.portraits import portraits
import dating_audio
import dating_data
import adb_install as adb_install_module
import spine_update

router = APIRouter()
FILES = (dating_data.RULES_OUT, dating_data.EVENTS_OUT, dating_data.COSTUMES_OUT)
_lock = threading.Lock()


def _bundles_with(pattern: str, log, device: str = "") -> list:
    """Paths of the original game bundles that hold the assets whose catalog key matches `pattern`, downloaded when needed. The game
    keeps all dating scenes in one bundle or (since its November 2026 update) one bundle per scene and kind; this finds either."""
    import re
    index = manager.get_or_load_index(configured_quality(), log) or {}
    strings, records = index.get("strings", []), index.get("records", [])
    wanted = re.compile(pattern, re.I)
    hashes = {strings[records[r][1]] for key, refs in index.get("assetsByExactKey", {}).items() if wanted.search(key)
              for r in (refs if isinstance(refs, list) else [refs])}
    if not hashes:
        raise RuntimeError("Could not find the dating bundles in the game's catalog")
    paths = []
    for target in sorted(hashes):
        path, _name, _hash = manager.fetch_bundle(target, configured_quality(), device or None, log)
        if not path:
            raise RuntimeError("Could not download a dating bundle")
        paths.append(path)
    return paths


def _dating_bundles(log, device: str = "") -> list:
    """The prefab bundles that carry every scene's touch rules."""
    return _bundles_with(r"^char/datingillust/illust_dating\d+(_\d+)?\.prefab$", log, device)


def _run_update(get_strings, device: str = ""):
    """The shared part of both updates: sound event names from `get_strings`, touch rules from the original dating bundle (CDN, or the phone as a fallback)."""
    if not _lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="The dating data is already being updated")
    try:
        with track("Updating the dating data", "setup") as t:
            try:
                summary = dating_data.update_dating_data(get_strings, lambda: _dating_bundles(t.log, device), t.log)
                dating_audio.reload_data()
                t.log(f"Dating data updated: {summary['scenes']} scenes, {summary['spots']} spots.", "success")
                return summary
            except Exception as exc:
                t.log(f"Could not update the dating data: {exc}", "error")
                raise HTTPException(status_code=502, detail=str(exc))
    finally:
        _lock.release()


@router.post("/api/tools/dating-data/update")
def update_dating_data(device_id: str = ""):
    """Rebuild the dating tables (touch rules and sizes, sound events, scene-to-sound-bank matches) from the connected phone and the game's CDN."""
    devices = manager.adb.get_devices()
    device = device_id or next((d["id"] for d in devices if d["status"] == "device"), "")
    if not device:
        if any(d["status"] == "unauthorized" for d in devices):
            raise HTTPException(status_code=400, detail="The phone is connected but has not allowed this computer. Accept the USB debugging prompt on the phone, then try again.")
        raise HTTPException(status_code=400, detail="No phone found. Connect it with USB debugging turned on, then try again.")
    if not manager.adb.check_game_installed(device):
        raise HTTPException(status_code=400, detail="Brown Dust 2 is not installed on the connected phone.")
    return _run_update(lambda: dating_data.strings_from_phone(manager.adb.adb_bin, device), device)


@router.get("/api/tools/adb")
def adb_info():
    """Whether adb (the phone connection) is available, and where it was found."""
    return {"found": manager.adb.is_adb_available(), "path": manager.adb.adb_bin}


@router.post("/api/tools/adb/install")
def adb_install():
    """Download Google's platform-tools into the data folder and use its adb."""
    with track("Downloading adb (phone connection)", "setup") as t:
        try:
            manager.adb.adb_bin = adb_install_module.install(t.log)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not download adb: {e}")
    return adb_info()


class ApkRequest(BaseModel):
    path: str


@router.post("/api/tools/dating-data/update-apk")
def update_dating_data_from_apk(req: ApkRequest):
    """The same update without a phone: the game's APK (or .xapk/.apks) on this computer supplies the sound event names."""
    return _run_update(lambda: dating_data.strings_from_apk_file(os.path.expanduser(req.path.strip().strip('"'))))


def _scenes() -> dict:
    """Scenes the touch rules know, how many have sounds (a sound bank costume with events) and which dating scenes of the library have no data yet."""
    from web.state import db
    known = {n for n in (dating_audio.scene_number(k) for k in (dating_audio.dating_rules_all() or {})) if n}
    with_sounds = sorted(n for n in known if dating_audio.scene_costume(n) and dating_audio.sound_events(dating_audio.scene_costume(n)))
    seen = {n for n in (dating_audio.scene_number(m.get("asset_key") or "") for m in db.index_rows()) if n}
    return {"scenes": len(known), "with_sounds": len(with_sounds), "scene_numbers": with_sounds, "new_scenes": sorted(seen - known)}


@router.get("/api/tools/dating-data")
def dating_data_info():
    """When the dating tables were last rebuilt and how much space they take (nothing is built-in: no files = no simulator data)."""
    found = [f for f in FILES if os.path.isfile(f)]
    return {"files": len(found), "bytes": sum(os.path.getsize(f) for f in found),
            "updated_at": max((os.path.getmtime(f) for f in found), default=None), **_scenes()}


_sounds_lock = threading.Lock()


@router.post("/api/tools/dating-data/sounds")
def download_all_dating_sounds():
    """Download and decode the sounds of every known dating scene (the banks are shared, so this is ~50 MB plus ~2 MB per voiced scene)."""
    if not _sounds_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="The dating sounds are already downloading")
    done, failed = [], []
    try:
        with track("Downloading the dating sounds", "setup") as t:
            numbers = _scenes()["scene_numbers"]
            for index, number in enumerate(numbers):
                scene = f"illust_dating{number}"
                t.log(f"Sounds of scene {number} ({index + 1}/{len(numbers)})", "info", int(index / max(1, len(numbers)) * 100))
                if manager.dating_audio_status(scene).get("cached"):
                    continue
                try:
                    manager.download_dating_audio(scene, quality=configured_quality(), log_cb=t.log)
                    done.append(number)
                except Exception as exc:
                    t.log(f"Could not get the sounds of {scene}: {exc}", "error")
                    failed.append(number)
            t.log(f"Dating sounds: {len(done)} scenes downloaded, {len(failed)} failed.", "success" if not failed else "warning")
            if failed:
                t.fail(f"{len(failed)} scene(s) failed")
            return {"downloaded": done, "failed": failed, **_scenes()}
    finally:
        _sounds_lock.release()


@router.delete("/api/tools/dating-data")
def delete_dating_data():
    for f in FILES:
        if os.path.isfile(f):
            os.remove(f)
    dating_audio.reload_data()
    emit_log("Dating data deleted; update it from the Tools menu to get the touch simulator back.", level="info")
    return dating_data_info()


CHARACTERS_STAMP = os.path.join(manager.work_dir, "characters_synced")


@router.get("/api/tools/characters")
def characters_info():
    chars = character_manager.characters
    return {"count": len(chars), "costumes": sum(len(c.get("costumes") or {}) for c in chars),
            "updated_at": os.path.getmtime(CHARACTERS_STAMP) if os.path.isfile(CHARACTERS_STAMP) else None,
            "portraits": portraits.costume_info()["count"]}


@router.delete("/api/tools/characters")
def delete_characters():
    """Forget every character, costume name, dating link and costume portrait; Update Characters rebuilds them from scratch."""
    character_manager.clear_characters()
    dating_audio.set_scene_links([])
    portraits.delete_costumes()
    if os.path.isfile(CHARACTERS_STAMP):
        os.remove(CHARACTERS_STAMP)
    emit_log("Character data deleted; use Update Characters to get it again from the website and the game.", level="info")
    return characters_info()


@router.post("/api/tools/characters/update")
def update_characters():
    """Refresh names, costumes and portraits from the community database (existing and custom entries are kept)."""
    with track("Updating characters and costume portraits", "setup") as t:
        t.log("Getting the character list from the community website...")
        try:
            result = character_manager.sync_from_web()
        except RuntimeError as exc:
            t.log(str(exc), "error")
            raise HTTPException(status_code=502, detail=str(exc))
        dating_audio.set_scene_links(character_manager.characters)
        open(CHARACTERS_STAMP, "w").close()
        os.utime(CHARACTERS_STAMP)
        t.log(f"Characters updated: {result['added']} added, {result['updated']} updated ({result['total']} total).", "success")
        portrait_error = ""
        portraits.update_extras(character_manager.characters, t.log)
        try:
            portraits.update_costumes(manager, configured_quality(), t.log)
        except Exception as exc:  # names are updated already: report the portraits separately
            portrait_error = str(exc)
            t.log(f"Could not update the costume portraits: {exc}", "error")
            t.fail(portrait_error)
        return {**result, **characters_info(), "portrait_error": portrait_error}


# ---- original dating scenes ------------------------------------------------------------------------------------------

_scene_lock = threading.Lock()


def _scene_title(number: int):
    """(character, costume name) of a scene from the website's links, else (None, None)."""
    for c in character_manager.characters:
        costume = (c.get("dating") or {}).get(f"illust_dating{number}")
        if costume:
            return c["name"], (c.get("costumes") or {}).get(costume) or costume
    return None, None


@router.get("/api/tools/dating-scenes")
def dating_scenes():
    """Every dating scene of the game (touch rules, or a link on the website) with its character and costume."""
    numbers = set(_scenes()["scene_numbers"]) | {dating_audio.scene_number(k) for k in (dating_audio.dating_rules_all() or {})}
    for c in character_manager.characters:
        numbers |= {dating_audio.scene_number(k) for k in (c.get("dating") or {})}
    out = []
    for n in sorted(x for x in numbers if x):
        character, costume = _scene_title(n)
        out.append({"scene": f"illust_dating{n}", "number": n, "character": character, "costume": costume})
    return {"scenes": out}


class SceneRequest(BaseModel):
    scene: str
    root: str  # a folder tab's folder: the scene's folders are written straight into it


@router.post("/api/tools/dating-scene")
def download_dating_scene(req: SceneRequest):
    """Download the original dating bundle (cached), take one scene out of it and write it as mod folders inside a folder tab."""
    import json
    import subprocess
    import sys
    number = dating_audio.scene_number(req.scene)
    root = os.path.abspath(os.path.expanduser(req.root))
    if not number:
        raise HTTPException(status_code=400, detail="Not a dating scene")
    if not any(os.path.realpath(root) == os.path.realpath(os.path.expanduser(t.get("path", ""))) for t in load_config().get("folder_tabs", [])):
        raise HTTPException(status_code=400, detail="Pick one of your folder tabs as the destination")
    if not _scene_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A dating scene is already being downloaded")
    try:
        with track(f"Extracting original dating scene {number}", "work") as t:
            return _export_scene(t, number, root)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        _scene_lock.release()


def _export_scene(t, number: int, root: str):
    import json
    import subprocess
    log = t.log
    paths = _bundles_with(rf"^skeletondata/illust_dating{number}(_\d+)?/", log)
    character, costume = _scene_title(number)
    title = f"{character} - {costume} (Dating) [Original]" if character else f"Dating scene {number} [Original]"
    proc = subprocess.run([*helper_command("dating_scene_export"), str(number), root, title, *paths],
                          capture_output=True, text=True, timeout=1800, env={**os.environ, "BD2_UNITY_VERSION": UNITY_VERSION})
    for line in proc.stdout.splitlines():
        if line.startswith("LOG "):
            log(line[4:])
    result = next((l[len("RESULT "):] for l in proc.stdout.splitlines() if l.startswith("RESULT ")), None)
    if proc.returncode or result is None:
        print(f"Dating scene helper failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
        raise RuntimeError((proc.stderr.strip().splitlines() or ["The scene could not be extracted"])[-1])
    folders = json.loads(result)
    t.log(f"Original dating scene {number} saved: {len(folders)} folder(s) in {root}.", "success")
    return {"folders": folders, "root": root}


_spine_lock = threading.Lock()


def _mod_roots() -> list:
    return [t["path"] for t in load_config().get("folder_tabs", []) if os.path.isdir(t.get("path", ""))]


@router.get("/api/tools/spine42")
def spine42_scan():
    """The game moved to Spine 4.2: how many mod skeletons are still 4.1 (they do not load in game until converted)."""
    with track("Checking the mod skeletons for Spine 4.2", "setup") as t:
        return spine_update.scan(_mod_roots(), t.log)


@router.post("/api/tools/spine42/update")
def spine42_update():
    """Convert every 4.1 skeleton in the mod folders to 4.2 (originals are kept in a `.spine41` folder beside each)."""
    if not _spine_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="The skeletons are already being updated")
    try:
        with track("Updating mod skeletons to Spine 4.2", "setup") as t:
            result = spine_update.update(_mod_roots(), t.log)
            t.log(f"Spine 4.2: {result['updated']} skeletons updated" + (f", {len(result['failed'])} damaged files left as they are" if result["failed"] else ""),
                  "success" if not result["failed"] else "warning")
            return result
    finally:
        _spine_lock.release()
