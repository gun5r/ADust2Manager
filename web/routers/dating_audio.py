import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from web.state import configured_quality, emit_log, manager, tracked
from dating_audio import dating_rules

router = APIRouter()
_locks: dict = {}


@router.get("/api/dating-rules/{scene}")
def get_dating_rules(scene: str):
    rules = dating_rules(scene)
    if rules is None:
        raise HTTPException(status_code=404, detail="No touch rules for this scene")
    return rules


@router.get("/api/dating-audio/{scene}")
def dating_audio_status(scene: str):
    return manager.dating_audio_status(scene)


@router.post("/api/dating-audio/{scene}/download")
@tracked("Downloading dating sounds", "download")
def download_dating_audio(scene: str):
    lock = _locks.setdefault(scene, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="This scene's audio is already downloading")
    try:
        status = manager.download_dating_audio(scene, quality=configured_quality(), log_cb=lambda m: emit_log(m, level="info"))
        emit_log(f"Dating audio ready for {scene}: sounds for {status['animations']} animations.", level="success")
        return status
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        emit_log(f"Could not get the dating audio for {scene}: {exc}", level="error")
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        lock.release()


@router.get("/api/dating-audio/{scene}/manifest")
def dating_audio_manifest(scene: str):
    manifest = manager.dating_manifest(scene)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Audio not downloaded for this scene")
    return manifest


@router.get("/api/dating-audio/{scene}/clip/{name}")
def dating_audio_clip(scene: str, name: str):
    path = manager.dating_clip_path(scene, name)
    if not path:
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="audio/wav")


_icon_lock = threading.Lock()


@router.get("/api/dating-tool-icon/{number}")
def dating_tool_icon(number: int):
    """The tool button picture of tool id `number - 1` (id 0 is the bare hand = icon 1); fetched from the game on first use."""
    try:
        with _icon_lock:
            path = manager.tool_icon_path(number, quality=configured_quality(), log_cb=lambda m: emit_log(m, level="info"))
    except Exception as exc:
        emit_log(f"Could not get the dating tool icons: {exc}", level="error")
        raise HTTPException(status_code=502, detail=str(exc))
    if not path:
        raise HTTPException(status_code=404, detail="No such tool icon")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=86400"})
