"""Mods that ship textures and an atlas but no skeleton: find donors, copy their skeleton, or take the game's original."""
import asyncio
import os
import re
import shutil
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from web.routers.library import inside_library
from web.state import configured_quality, db, emit_log, manager, track

router = APIRouter()
SKELETON = re.compile(r"\.(?:skel|skel\.bytes|json)$", re.I)


def _skeleton_files(folder: str) -> list:
    return [f for f in os.listdir(folder) if SKELETON.search(f) and not f.startswith(".")]


def _target_name(folder: str) -> str:
    """An existing skeleton keeps its name; otherwise it must sit next to the atlas under the atlas's own name."""
    existing = next((f for f in sorted(os.listdir(folder)) if f.lower().endswith((".skel", ".skel.bytes")) and not f.startswith(".")), None)
    if existing:
        return existing
    atlas = next((f for f in sorted(os.listdir(folder)) if f.lower().endswith(".atlas") and not f.startswith(".")), None)
    if atlas:
        return atlas[:-len(".atlas")] + ".skel"
    keys = manager.extract_mod_asset_key({"folder_path": folder, "files": os.listdir(folder)})
    return f"{keys}.skel"


def _donors_for(keys: set, me: str, rows: list) -> list:
    donors = []
    for row in rows:
        path = row.get("folder_path") or ""
        if not keys & set(row.get("asset_keys") or [row.get("asset_key")]) or os.path.realpath(path) == me:
            continue
        skels = [f for f in row.get("files", []) if f.lower().endswith((".skel", ".skel.bytes"))]
        if skels:
            donors.append({"name": row.get("name"), "folder_path": path, "skeleton": skels[0], "category": row.get("category"), "mtime": 0})
    return donors


@router.get("/api/mod/skeleton-donors")
def skeleton_donors(folder: str = Query(...)):
    """Other mods of the same asset that have a binary skeleton, newest first."""
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail="Mod folder not found")
    from mod_assets import asset_keys
    donors = _donors_for(set(asset_keys(os.listdir(folder))), os.path.realpath(folder), db.index_rows())
    for d in donors:
        try:
            d["mtime"] = os.path.getmtime(os.path.join(d["folder_path"], d["skeleton"]))
        except OSError:
            d["mtime"] = 0
    donors.sort(key=lambda d: -d["mtime"])
    return {"donors": donors}


@router.get("/api/mods/skeleton-scan")
def skeleton_scan(root: Optional[str] = None):
    """Every mod with textures or an atlas but no skeleton, each with the mods that could lend one."""
    rows = db.index_rows()
    found = []
    for row in rows:
        files = [f.lower() for f in row.get("files", [])]
        if row.get("is_multi") or not any(f.endswith((".atlas", ".png")) for f in files) or any(SKELETON.search(f) for f in files):
            continue
        if root and row.get("root") != root:
            continue
        keys = set(row.get("asset_keys") or [row.get("asset_key")])
        found.append({"name": row.get("name"), "folder_path": row.get("folder_path"), "asset_key": row.get("asset_key"),
                      "donors": _donors_for(keys, os.path.realpath(row.get("folder_path") or ""), rows)[:12]})
    return {"mods": found}


class FixSkeletonRequest(BaseModel):
    folder: str
    donor_folder: Optional[str] = None  # None = download the game's original


@router.post("/api/mod/fix-skeleton")
async def fix_skeleton(req: FixSkeletonRequest):
    folder = os.path.abspath(req.folder)
    if not os.path.isdir(folder) or not inside_library(folder):
        raise HTTPException(status_code=400, detail="Mod folder not found in the library")
    target = os.path.join(folder, _target_name(folder))
    if os.path.exists(target) and not os.path.exists(target + ".bak"):
        shutil.copyfile(target, target + ".bak")  # the replaced skeleton stays recoverable (once; a .bak never matches the scanner)
    loop = asyncio.get_event_loop()
    if req.donor_folder:
        donor = os.path.abspath(req.donor_folder)
        if not os.path.isdir(donor) or not inside_library(donor):
            raise HTTPException(status_code=400, detail="Donor folder not found in the library")
        source = next((os.path.join(donor, f) for f in _skeleton_files(donor) if f.lower().endswith((".skel", ".skel.bytes"))), None)
        if not source:
            raise HTTPException(status_code=400, detail="The donor has no skeleton")
        shutil.copyfile(source, target)
        origin = f"mod '{os.path.basename(donor)}'"
    else:
        with track(f"Downloading the original skeleton for {os.path.basename(folder)}", "download") as t:
            t.log(f"Downloading the original skeleton for {os.path.basename(folder)}...", "start")
            data, reason = await loop.run_in_executor(None, manager.original_skeleton, folder, configured_quality(), t.log)
            if data is None:
                raise HTTPException(status_code=502, detail=reason)
        with open(target, "wb") as out:
            out.write(data)
        origin = "the game files"
    message = f"Skeleton {os.path.basename(target)} copied from {origin}"
    emit_log(f"SUCCESS: {message}", level="success")
    return {"status": "success", "message": message, "file": os.path.basename(target)}
