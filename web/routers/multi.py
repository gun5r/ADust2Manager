import asyncio
import os
from fastapi import APIRouter, HTTPException, Query
from mod_assets import asset_keys
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from web.state import manager

router = APIRouter()


@router.get("/api/multi/tree")
def get_multi_mod_tree_endpoint(folder_path: str = Query(...), mod_name: Optional[str] = Query(None)):
    """
    Returns the organized folder tree, option categories, previews and variants for a multi mod.
    """
    tree_data = manager.get_multi_mod_tree(folder_path, mod_name=mod_name)
    return {"status": "ok", **tree_data}


class PreviewVariantRequest(BaseModel):
    variant_path: str
    mod_name: Optional[str] = ""


@router.post("/api/multi/preview-variant")
async def preview_multi_variant_endpoint(req: PreviewVariantRequest):
    """
    Extracts a selected variant archive on-demand into multi_preview_cache
    so the Spine player can inspect its skeleton and textures.
    """
    loop = asyncio.get_event_loop()
    success, msg, info = await loop.run_in_executor(
        None,
        manager.extract_multi_variant,
        req.variant_path,
        req.mod_name or ""
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "ok", "message": msg, **info}


class PrepareMultiSelectionRequest(BaseModel):
    variants: List[Dict[str, Any]]
    mod_name: str
    quality: Optional[str] = "HD"


@router.post("/api/multi/prepare-selections")
async def prepare_multi_selections_endpoint(req: PrepareMultiSelectionRequest):
    """
    Extracts all chosen variants for the multi mod into individual prepared folders,
    ready to be queued and bundled.
    """
    loop = asyncio.get_event_loop()
    prepared_items = []
    seen_paths = set()
    seen_keys = set()
    if not req.variants:
        raise HTTPException(status_code=400, detail="Select at least one variant")
    for var in req.variants:
        v_path = var.get("full_path") or var.get("path")
        if not isinstance(v_path, str) or not v_path.strip():
            raise HTTPException(status_code=400, detail="Variant is missing its folder path")
        v_path = os.path.abspath(v_path)
        if v_path in seen_paths:
            continue
        seen_paths.add(v_path)
        v_name = var.get("name") or os.path.basename(v_path)
        success, msg, info = await loop.run_in_executor(
            None,
            manager.extract_multi_variant,
            v_path,
            req.mod_name
        )
        if not success:
            raise HTTPException(status_code=400, detail=msg)
        if success:
            variant_files = info.get("files", [])
            keys = asset_keys(variant_files)
            overlaps = seen_keys.intersection(keys)
            if overlaps:
                raise HTTPException(status_code=400, detail=f"Conflicting replacement assets: {', '.join(sorted(overlaps))}")
            seen_keys.update(keys)
            asset_k = manager.extract_mod_asset_key({
                "folder_path": info["folder_path"],
                "files": variant_files,
                "asset_stem": info.get("stem") or v_name,
                "name": v_name
            })
            prepared_items.append({
                "name": f"{req.mod_name} [{v_name}]",
                "folder_path": info["folder_path"],
                "source_folder": v_path,  # the variant's own folder: where its portrait is kept
                "character": var.get("character") or req.mod_name,
                "variant_name": v_name,
                "asset_keys": keys,
                "files": variant_files,
                "asset_stem": info.get("stem") or v_name,
                "asset_key": asset_k
            })
    return {"status": "ok", "items": prepared_items}
