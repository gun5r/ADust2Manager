from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web.state import character_manager, emit_log, manager

router = APIRouter()


@router.get("/api/cache-info")
def get_cache_info():
    return manager.get_cache_stats()


@router.get("/api/cache/repacked-mods")
def get_repacked_mods():
    mods = manager.get_cached_repacked_mods()
    for m in mods:
        files_hint = list(m.get("files") or [])
        if m.get("asset_key"):
            files_hint.append(m["asset_key"])
        if m.get("asset_stem"):
            files_hint.append(m["asset_stem"])
        matched_char = character_manager.match_character(m.get("mod_name", ""), files_hint)
        m["character"] = matched_char if matched_char else "Others"
        c_key, c_name, c_order = manager.classify_mod_category(m.get("mod_name", ""), files_hint, False)
        m["category"] = c_key
        m["category_name"] = c_name
    return {"status": "ok", "count": len(mods), "mods": mods}


class DeleteRepackedModRequest(BaseModel):
    folder_name: str


@router.post("/api/cache/repacked-mods/delete")
def delete_repacked_mod_endpoint(req: DeleteRepackedModRequest):
    ok = manager.delete_repacked_mod(req.folder_name)
    if ok:
        emit_log(f"Deleted cached mod bundle: {req.folder_name}", level="info")
        return {"status": "ok", "deleted": req.folder_name}
    raise HTTPException(status_code=404, detail="Folder not found or deletion failed")


class CacheClearRequest(BaseModel):
    clear_originals: bool = True
    clear_repacked: bool = True
    clear_catalogs: bool = False
    clear_thumbs: bool = False
    clear_audio: bool = False


@router.post("/api/cache-clear")
def clear_cache_endpoint(req: CacheClearRequest):
    res = manager.clear_cache(
        clear_originals=req.clear_originals,
        clear_repacked=req.clear_repacked,
        clear_catalogs=req.clear_catalogs,
        clear_thumbs=req.clear_thumbs,
        clear_audio=req.clear_audio
    )
    return {"status": "ok", "result": res}
