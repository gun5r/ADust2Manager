import asyncio
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional
import mod_health
import skel_convert
import skel_files
from web.state import emit_log, manager

router = APIRouter()


class MergeSpineRequest(BaseModel):
    mod_folder: str
    target_count: Optional[int] = None


@router.post("/api/mod/merge-spine")
async def merge_spine_endpoint(req: MergeSpineRequest):
    folder = os.path.abspath(req.mod_folder)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail="Mod folder not found")

    def log_cb(msg):
        emit_log(msg, level="info")

    emit_log(f"Starting Spine texture merge for {os.path.basename(folder)}...", level="start")
    loop = asyncio.get_event_loop()
    success, msg = await loop.run_in_executor(
        None, manager.merge_spine_mod, folder, req.target_count, log_cb
    )
    if success:
        emit_log(f"SUCCESS: {msg}", level="success")
        return {"status": "success", "message": msg}
    else:
        emit_log(f"FAILED: {msg}", level="error")
        raise HTTPException(status_code=500, detail=msg)


class RevertMergeRequest(BaseModel):
    mod_folder: str


@router.post("/api/mod/revert-merge")
async def revert_merge_endpoint(req: RevertMergeRequest):
    folder = os.path.abspath(req.mod_folder)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail="Mod folder not found")

    def log_cb(msg):
        emit_log(msg, level="info")

    emit_log(f"Reverting Spine merge for {os.path.basename(folder)}...", level="start")
    loop = asyncio.get_event_loop()
    success, msg = await loop.run_in_executor(
        None, manager.revert_spine_mod, folder, log_cb
    )
    if success:
        emit_log(f"SUCCESS: {msg}", level="success")
        return {"status": "success", "message": msg}
    else:
        emit_log(f"FAILED: {msg}", level="error")
        raise HTTPException(status_code=500, detail=msg)


class SanitizeModRequest(BaseModel):
    mod_folder: str


@router.post("/api/mod/sanitize")
async def sanitize_mod_endpoint(req: SanitizeModRequest):
    folder = os.path.abspath(req.mod_folder)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail="Mod folder not found")

    def log_cb(msg):
        emit_log(msg, level="info")

    emit_log(f"Sanitizing filenames and atlas references for {os.path.basename(folder)}...", level="info")
    loop = asyncio.get_event_loop()
    success, msg = await loop.run_in_executor(
        None, manager.sanitize_mod_filenames, folder, log_cb
    )
    return {"status": "success" if success else "error", "message": msg}


@router.get("/api/spine-files")
def get_spine_files(folder_path: str = Query(...)):
    """
    Returns paths to files inside the mod folder for Spine animation preview.
    """
    import spine_merger
    folder = os.path.abspath(folder_path)
    if not os.path.exists(folder):
        raise HTTPException(status_code=404, detail="Folder not found")

    rel_files = []
    png_count = 0
    for f in os.listdir(folder):
        if not f.startswith("."):
            rel_files.append(f)
            if f.lower().endswith(".png"):
                png_count += 1
    has_backup = spine_merger.has_backup(folder)
    return {
        "folder": folder, 
        "files": sorted(rel_files),
        "png_count": png_count,
        "has_backup": has_backup
    }


@router.get("/api/spine-file-content")
def get_spine_file_content(file_path: str = Query(...)):
    """
    Serves a specific texture or atlas file for live canvas preview.
    """
    full_path = os.path.abspath(file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)


@router.get("/api/mod-assets/{folder_b64}/{filename:path}")
def serve_mod_asset(folder_b64: str, filename: str, max: int = Query(0, ge=0, le=8192)):
    """
    Serves files directly from the mod folder using a base64 encoded directory path.
    This enables Spine Player to resolve all relative page images (e.g. illust_dating4.png,
    illust_dating4_2.png) automatically without 404 errors.
    """
    import base64
    try:
        # Pad base64 string if necessary
        padded_b64 = folder_b64 + "=" * ((4 - len(folder_b64) % 4) % 4)
        folder_path = base64.urlsafe_b64decode(padded_b64.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid folder encoding: {e}")

    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail=f"Mod directory does not exist: {folder_path}")

    target_path = os.path.join(folder_path, filename)

    # Direct match or case/Unicode-insensitive search
    if not os.path.exists(target_path):
        import unicodedata
        dir_name = os.path.dirname(target_path)
        base_target = unicodedata.normalize('NFC', os.path.basename(target_path)).lower()
        if os.path.isdir(dir_name):
            for entry in os.listdir(dir_name):
                if unicodedata.normalize('NFC', entry).lower() == base_target:
                    target_path = os.path.join(dir_name, entry)
                    break

    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"Asset not found: {filename}")

    # Proper MIME types for browser canvas / WebGL
    lower_name = filename.lower()
    media_type = "application/octet-stream"
    if lower_name.endswith(".png"):
        media_type = "image/png"
    elif lower_name.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif lower_name.endswith((".atlas", ".atlas.txt", ".txt")):
        media_type = "text/plain"
    elif lower_name.endswith(".json"):
        media_type = "application/json"
    elif lower_name.endswith((".skel", ".skel.bytes")):
        media_type = "application/octet-stream"

    if max and lower_name.endswith(".png"):  # portrait rendering asks for smaller textures (see core/portraits.py)
        from web.routers.portraits import portraits
        target_path = portraits.reduced_texture(target_path, max)
    elif max and lower_name.endswith(".atlas"):  # ...and the atlas that goes with them
        from fastapi.responses import PlainTextResponse
        from portraits import reduced_atlas
        with open(target_path, encoding="utf-8", errors="replace") as f:
            return PlainTextResponse(reduced_atlas(f.read(), folder_path, max))
    if lower_name.endswith((".skel", ".skel.bytes", ".json")):
        converted = _current_skeleton(target_path)  # the player is Spine 4.2: older skeletons are converted on the way
        if converted is not None:
            return Response(converted, media_type=media_type)
    return FileResponse(target_path, media_type=media_type)


def _skel_cache() -> str:
    return os.path.join(manager.work_dir, "skel42_cache")


def _current_skeleton(path: str):
    """The skeleton file as Spine 4.2 reads it, or None when it is served as it is (already 4.2, not a skeleton, damaged)."""
    try:
        return skel_files.current_bytes(path, _skel_cache())
    except (OSError, ValueError, skel_convert.SkelError):
        return None


@router.get("/api/mods/health")
def mod_health_endpoint(folder: str = Query(...)):
    """Textures and skeletons of a mod folder that are cut off (an incomplete download): the preview warns about them."""
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Mod directory does not exist")
    return {"damaged": mod_health.damaged_files(folder, _skel_cache())}


@router.get("/api/mods/file")
def get_mod_file_endpoint(folder: str = Query(...), file: str = Query(...)):
    """Direct query parameter file endpoint for compatibility."""
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Mod directory does not exist")
    target_path = os.path.join(folder, file)
    if not os.path.exists(target_path):
        for entry in os.listdir(folder):
            if entry.lower() == file.lower():
                target_path = os.path.join(folder, entry)
                break
    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file}")

    lower_name = file.lower()
    media_type = "application/octet-stream"
    if lower_name.endswith(".png"):
        media_type = "image/png"
    elif lower_name.endswith((".atlas", ".atlas.txt", ".txt")):
        media_type = "text/plain"
    elif lower_name.endswith(".json"):
        media_type = "application/json"
    return FileResponse(target_path, media_type=media_type)
