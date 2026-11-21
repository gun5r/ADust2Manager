from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from web.state import db, emit_log, manager
from portraits import Portraits

router = APIRouter()
portraits = Portraits(manager.work_dir)


@router.get("/api/portraits/costume/{costume_id}.png")
def costume_portrait(costume_id: str):
    path = portraits.costume_path(costume_id)
    if not path:
        raise HTTPException(status_code=404, detail="No portrait for this costume")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=600"})


@router.get("/api/portraits/costumes")
def costume_portrait_list():
    """Costume ids that have a portrait."""
    return {"costumes": sorted(f[:-4] for f in __import__("os").listdir(portraits.costume_dir) if f.endswith(".png"))}


@router.get("/api/portraits/mods")
def mod_portrait_list():
    return {"mods": portraits.mod_versions()}


@router.get("/api/portraits/mod")
def mod_portrait(folder: str = Query(...)):
    path = portraits.mod_path(folder)
    if not path:
        raise HTTPException(status_code=404, detail="No portrait for this mod")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


def _known_folder(folder: str) -> bool:
    """A mod folder of the index, or a variant folder inside an indexed multimod (those are not listed on their own)."""
    import os
    current = os.path.normpath(folder)
    for _ in range(6):
        if db.has_folder(current):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return False


@router.post("/api/portraits/mod")
async def save_mod_portrait(request: Request, folder: str = Query(...)):
    if not _known_folder(folder):
        raise HTTPException(status_code=404, detail="Folder is not in the mod index")
    try:
        portraits.save_mod(folder, await request.body())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@router.get("/api/tools/portraits")
def mod_portrait_info():
    return portraits.mod_info()


@router.delete("/api/tools/portraits")
def delete_mod_portraits():
    portraits.delete_mods()
    emit_log("Mod portraits deleted.", level="info")
    return portraits.mod_info()
