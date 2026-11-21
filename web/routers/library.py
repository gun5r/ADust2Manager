import re
import asyncio
import hashlib
import os
import shutil
import threading
import time
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from web.state import character_manager, db, emit_log, load_config, manager, tracked

router = APIRouter()


class ScanRequest(BaseModel):
    mods_dir: str
    force_multi: Optional[bool] = False


class MultiScanRequest(BaseModel):
    mods_dirs: List[str]
    force_multi_map: Optional[Dict[str, bool]] = {}


@router.post("/api/scan")
@tracked("Scanning a mod folder", "scan")
def scan_mods(req: ScanRequest):
    manager.clear_scan_cache()
    mods_dir = os.path.expanduser(req.mods_dir)
    if not os.path.exists(mods_dir):
        os.makedirs(mods_dir, exist_ok=True)
    mods = manager.scan_mods_folder(mods_dir, force_multi=bool(req.force_multi), invalidate=True)
    for m in mods:
        if not m.get("asset_key"):
            m["asset_key"] = manager.extract_mod_asset_key(m)
        files_hint = list(m.get("files", []))
        if m.get("asset_key"):
            files_hint.append(m["asset_key"])
        m["character"] = character_manager.match_character(m.get("name", ""), files_hint) or "Others"
    db.replace_mods(os.path.abspath(mods_dir), mods, time.time())
    return {"mods_dir": mods_dir, "count": len(mods), "mods": mods}


@router.post("/api/scan_all")
@tracked("Scanning the mod folders", "scan")
def scan_all_mods(req: MultiScanRequest):
    manager.clear_scan_cache()
    all_mods = []
    seen_keys = set()
    force_map = req.force_multi_map or {}
    for raw_dir in req.mods_dirs:
        if not raw_dir:
            continue
        d = os.path.expanduser(raw_dir.strip())
        if not os.path.exists(d):
            db.replace_mods(os.path.abspath(d), [], time.time())  # a renamed or deleted folder no longer lists its old mods
            continue
        real_d = os.path.realpath(d)
        abs_d = os.path.abspath(d)
        is_forced = bool(
            force_map.get(raw_dir) or 
            force_map.get(d) or 
            force_map.get(real_d) or 
            force_map.get(abs_d) or
            any(v for k, v in force_map.items() if k and os.path.realpath(os.path.expanduser(k)) == real_d)
        )
        folder_mods = manager.scan_mods_folder(d, force_multi=is_forced, invalidate=True)
        folder_enriched = []
        for m in folder_mods:
            mod_key = (os.path.abspath(m["folder_path"]), m.get("id") or m.get("name"))
            if mod_key not in seen_keys:
                seen_keys.add(mod_key)
                if not m.get("asset_key"):
                    m["asset_key"] = manager.extract_mod_asset_key(m)
                files_hint = list(m.get("files", []))
                if m.get("asset_key"):
                    files_hint.append(m["asset_key"])
                m["character"] = character_manager.match_character(m.get("name", ""), files_hint) or "Others"
                all_mods.append(m)
                folder_enriched.append(m)
        db.replace_mods(abs_d, folder_enriched, time.time())
    return {"count": len(all_mods), "mods": all_mods}


@router.get("/api/mods")
def query_mods(q: str = "", character: Optional[str] = None, category: Optional[str] = None,
               root: Optional[str] = None, sort: str = "name", offset: int = 0, limit: int = 100):
    """Paginated, filtered view of the mods found by the last scan of each folder."""
    return db.query_mods(q, character, category, root, sort, offset, limit)


@router.get("/api/mods/index")
def mods_index(root: Optional[str] = None):
    """All indexed mods in a compact form; the client groups, filters and virtualizes them itself."""
    return {"mods": db.index_rows(root)}


@router.get("/api/mods/installed")
def installed_mods():
    """Index records (asset keys, folders) for mods marked installed, plus installed names the index does not know."""
    names = load_config().get("installed_mods", [])
    found = db.mods_by_names(names)
    known = {m.get("name") for m in found}
    return {"mods": found, "missing": [n for n in names if n not in known]}

@router.get("/api/mods/thumb")
def mod_thumb(folder: str = Query(...), file: str = Query(...), size: int = 256):
    """Cached WebP thumbnail of a texture in a scanned mod folder (only indexed folders are served)."""
    if not db.has_folder(folder):
        raise HTTPException(status_code=404, detail="Folder is not in the mod index")
    if os.path.basename(file) != file or not file.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="Only PNG files in the mod folder can be thumbnailed")
    source = os.path.join(folder, file)
    if not os.path.isfile(source):
        raise HTTPException(status_code=404, detail="File not found")
    size = max(64, min(size, 1024))
    info = os.stat(source)
    key = hashlib.sha1(f"{source}|{info.st_mtime_ns}|{info.st_size}|{size}".encode("utf-8")).hexdigest()
    thumbs_dir = manager.thumbs_dir
    target = os.path.join(thumbs_dir, key + ".webp")
    if not os.path.exists(target):
        from PIL import Image
        os.makedirs(thumbs_dir, exist_ok=True)
        try:
            with Image.open(source) as image:
                image.thumbnail((size, size))
                temporary = f"{target}.{threading.get_ident()}.tmp"
                image.convert("RGBA").save(temporary, "WEBP", quality=80)
            os.replace(temporary, target)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Cannot read image: {e}")
    return FileResponse(target, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

@router.get("/api/mods/facets")
def mod_facets():
    return db.mod_facets()


@router.get("/api/characters")
def get_characters():
    return {"characters": character_manager.characters}


class AddCharacterRequest(BaseModel):
    name: str
    costume_id: Optional[str] = ""
    image_url: Optional[str] = ""


@router.post("/api/characters/add")
def add_character(req: AddCharacterRequest):
    try:
        char = character_manager.add_or_update_character(req.name, req.costume_id, req.image_url)
        return {"status": "ok", "character": char, "characters": character_manager.characters}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/characters/sync_web")
async def sync_characters_from_web():
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, character_manager.sync_from_web)
        return {"status": "ok", "result": res, "characters": character_manager.characters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CheckDuplicatesRequest(BaseModel):
    mods_dirs: Optional[List[str]] = None


@router.post("/api/mods/check-duplicates")
def check_duplicates_endpoint(req: CheckDuplicatesRequest):
    cfg = load_config()
    folder_tabs = cfg.get("folder_tabs", [])
    dirs = req.mods_dirs or [t.get("path") for t in folder_tabs if t.get("path")]
    all_mods = []
    seen = set()
    for d in dirs:
        if d and os.path.exists(d):
            for m in manager.scan_mods_folder(d):
                fp = os.path.abspath(m["folder_path"])
                if fp not in seen:
                    seen.add(fp)
                    all_mods.append(m)
    res = manager.detect_duplicates_and_collisions(all_mods)
    return {"status": "ok", "folder_tabs": folder_tabs, **res}


def inside_library(path: str) -> bool:
    """True when `path` is strictly inside one of the configured mod folders (never a folder root, never elsewhere)."""
    target = os.path.realpath(path)
    for tab in load_config().get("folder_tabs", []):
        root = tab.get("path")
        if not root:
            continue
        root = os.path.realpath(os.path.expanduser(root))
        if target != root and target.startswith(root.rstrip(os.sep) + os.sep):
            return True
    return False


class DeleteFolderRequest(BaseModel):
    folder_path: str


@router.post("/api/mod/delete-folder")
def delete_folder_endpoint(req: DeleteFolderRequest):
    import shutil
    target = os.path.abspath(req.folder_path)
    if not os.path.exists(target) or not os.path.isdir(target):
        raise HTTPException(status_code=404, detail="Folder not found")
    if not inside_library(target):
        raise HTTPException(status_code=403, detail="Folder is not inside a configured mod folder")
    shutil.rmtree(target, ignore_errors=True)
    db.remove_folders([target])
    manager.clear_scan_cache()
    emit_log(f"Deleted duplicate mod folder: {target}", level="info")
    return {"status": "ok", "deleted": target}


class DeleteFoldersRequest(BaseModel):
    folder_paths: List[str]


@router.post("/api/mod/delete-folders")
def delete_folders_endpoint(req: DeleteFoldersRequest):
    import shutil
    deleted = []
    failed = []
    for fp in req.folder_paths:
        if not fp:
            continue
        target = os.path.abspath(fp)
        if not os.path.exists(target) or not os.path.isdir(target):
            continue
        if not inside_library(target):
            failed.append({"path": target, "error": "Folder is not inside a configured mod folder"})
            continue
        try:
            shutil.rmtree(target, ignore_errors=True)
            deleted.append(target)
        except Exception as e:
            failed.append({"path": target, "error": str(e)})

    db.remove_folders(deleted)
    manager.clear_scan_cache()
    emit_log(f"Batch deleted {len(deleted)} duplicate mod folder(s)", level="info")
    return {"status": "ok", "deleted": deleted, "failed": failed}


class RenameFolderRequest(BaseModel):
    folder_path: str
    new_name: str


@router.post("/api/mod/rename-folder")
def rename_folder_endpoint(req: RenameFolderRequest):
    target = os.path.abspath(req.folder_path)
    if not os.path.exists(target) or not os.path.isdir(target):
        raise HTTPException(status_code=404, detail="Source folder not found")
    if not inside_library(target):
        raise HTTPException(status_code=403, detail="Folder is not inside a configured mod folder")
    safe_new_name = os.path.basename(req.new_name.strip())
    if not safe_new_name or safe_new_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid new folder name")

    parent_dir = os.path.dirname(target)
    new_path = os.path.join(parent_dir, safe_new_name)

    # If destination already exists on disk, auto-increment _1, _2, _3... until a free name is found
    if os.path.exists(new_path) and os.path.abspath(new_path) != target:
        base_stem = re.sub(r'(_\d+)+$', '', safe_new_name)
        counter = 1
        candidate = f"{base_stem}_{counter}"
        candidate_path = os.path.join(parent_dir, candidate)
        while os.path.exists(candidate_path) and os.path.abspath(candidate_path) != target:
            counter += 1
            candidate = f"{base_stem}_{counter}"
            candidate_path = os.path.join(parent_dir, candidate)
        safe_new_name = candidate
        new_path = candidate_path

    os.rename(target, new_path)
    manager.clear_scan_cache()
    emit_log(f"Renamed mod folder '{os.path.basename(target)}' to '{safe_new_name}'", level="info")
    return {"status": "ok", "old_path": target, "new_path": new_path, "new_name": safe_new_name}
