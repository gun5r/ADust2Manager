import asyncio
import os
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from web.state import db, emit_log, load_config, manager, save_config, track

router = APIRouter()


class InstallRequest(BaseModel):
    mod_folder: str
    device_id: str
    quality: str = "HD"


@router.post("/api/install")
async def install_mod(req: InstallRequest):
    mod_folder = os.path.abspath(req.mod_folder)
    if not os.path.exists(mod_folder):
        raise HTTPException(status_code=400, detail="Mod directory does not exist")

    loop = asyncio.get_event_loop()
    with track(f"Installing {os.path.basename(mod_folder)} on the phone", "install") as t:
        t.log(f"Starting installation of {os.path.basename(mod_folder)} to {req.device_id}...", "start")
        success, msg = await loop.run_in_executor(
            None,
            manager.install_mod_to_phone,
            mod_folder,
            req.device_id,
            req.quality,
            t.log
        )
        if not success:
            t.fail(msg)

    if success:
        cfg = load_config()
        mod_basename = os.path.basename(mod_folder)
        settings = cfg.get("settings") or {}
        if settings.get("auto_mark_installed", True):
            if mod_basename not in cfg.setdefault("installed_mods", []):
                cfg["installed_mods"].append(mod_basename)
                save_config(cfg)
        emit_log(f"SUCCESS: {msg}", level="success")
        return {"status": "success", "message": msg, "installed_mods": cfg.get("installed_mods", [])}
    else:
        emit_log(f"FAILED: {msg}", level="error")
        raise HTTPException(status_code=500, detail=msg)


class BatchInstallRequest(BaseModel):
    mod_folders: List[str]
    device_id: str
    quality: str = "HD"


@router.post("/api/install-batch")
async def install_batch(req: BatchInstallRequest):
    results = []
    total = len(req.mod_folders)
    loop = asyncio.get_event_loop()
    with track(f"Installing {total} mods on the phone", "install") as t:
        t.log(f"Starting batch install of {total} mods...", "start")
        for idx, folder in enumerate(req.mod_folders):
            t.log(f"[{idx+1}/{total}] Installing {os.path.basename(folder)}...", "info", int((idx / total) * 100))
            success, msg = await loop.run_in_executor(
                None,
                manager.install_mod_to_phone,
                folder,
                req.device_id,
                req.quality,
                t.log
            )
            results.append({
                "folder": folder,
                "success": success,
                "message": msg
            })
        if not all(r["success"] for r in results):
            t.fail(f"{sum(1 for r in results if not r['success'])} of {total} failed")

    cfg = load_config()
    settings = cfg.get("settings") or {}
    auto_mark = settings.get("auto_mark_installed", True)
    updated_cfg = False
    for res in results:
        if res["success"] and auto_mark:
            mod_b = os.path.basename(res["folder"])
            if mod_b not in cfg.setdefault("installed_mods", []):
                cfg["installed_mods"].append(mod_b)
                updated_cfg = True
    if updated_cfg:
        save_config(cfg)

    emit_log("Batch installation completed!", level="success", progress=100)
    return {"results": results, "installed_mods": cfg.get("installed_mods", [])}


# Active preparation cancellation tracker
active_preparations_lock = threading.Lock()


active_preparations: Dict[str, threading.Event] = {}


def register_active_prep(mod_folder: str, job_id: Optional[str] = None) -> threading.Event:
    ev = threading.Event()
    norm = os.path.abspath(mod_folder)
    with active_preparations_lock:
        active_preparations[norm] = ev
        if job_id:
            active_preparations[job_id] = ev
    return ev


def cancel_active_prep(mod_folder: Optional[str] = None, job_id: Optional[str] = None) -> bool:
    found = False
    with active_preparations_lock:
        if mod_folder:
            norm = os.path.abspath(mod_folder)
            ev = active_preparations.get(norm)
            if ev:
                ev.set()
                found = True
        if job_id:
            ev = active_preparations.get(job_id)
            if ev:
                ev.set()
                found = True
    return found


def unregister_active_prep(mod_folder: str, job_id: Optional[str] = None):
    norm = os.path.abspath(mod_folder)
    with active_preparations_lock:
        active_preparations.pop(norm, None)
        if job_id:
            active_preparations.pop(job_id, None)


class PrepareModRequest(BaseModel):
    mod_folder: Optional[str] = None
    mod_folders: Optional[List[str]] = None
    quality: Optional[str] = "HD"
    job_id: Optional[str] = None


@router.post("/api/mod/prepare")
async def api_prepare_mod(req: PrepareModRequest):
    target_target = req.mod_folders if (req.mod_folders and len(req.mod_folders) > 0) else req.mod_folder
    if not target_target:
        raise HTTPException(status_code=400, detail="Missing mod_folder or mod_folders")

    if isinstance(target_target, list):
        for f in target_target:
            if not os.path.exists(os.path.abspath(f)):
                raise HTTPException(status_code=400, detail=f"Folder not found: {f}")
        norm_key = os.path.abspath(target_target[0])
    else:
        norm_key = os.path.abspath(target_target)
        if not os.path.exists(norm_key):
            raise HTTPException(status_code=400, detail=f"Folder not found: {norm_key}")

    cancel_ev = register_active_prep(norm_key, req.job_id)
    loop = asyncio.get_event_loop()
    label = os.path.basename(norm_key) + (f" (+{len(target_target) - 1} sharing its bundle)" if isinstance(target_target, list) and len(target_target) > 1 else "")
    with track(f"Preparing {label}", "prepare") as t:
        try:
            success, prep_data, msg = await loop.run_in_executor(
                None,
                manager.prepare_mod,
                target_target,
                req.quality,
                t.log,
                cancel_ev.is_set
            )
        finally:
            unregister_active_prep(norm_key, req.job_id)
        if not success:
            t.cancel() if cancel_ev.is_set() else t.fail(msg)

    if not success:
        return {"success": False, "error": msg, "cancelled": cancel_ev.is_set()}
    return {"success": True, "data": prep_data, "message": msg}


class CancelPrepareRequest(BaseModel):
    mod_folder: Optional[str] = None
    job_id: Optional[str] = None


@router.post("/api/mod/cancel-prepare")
def api_cancel_prepare(req: CancelPrepareRequest):
    cancelled = cancel_active_prep(req.mod_folder, req.job_id)
    name = os.path.basename(req.mod_folder) if req.mod_folder else (req.job_id or "mod")
    if cancelled:
        emit_log(f"Preparation cancelled for: {name}", level="warning")
    return {"status": "ok", "cancelled": cancelled}


class TransferModRequest(BaseModel):
    device_id: str
    bundle_name: str
    bundle_hash: str
    repacked_path: str
    mod_name: Optional[str] = ""
    mod_names: Optional[List[str]] = None
    mod_folder: Optional[str] = ""


@router.post("/api/mod/transfer")
async def api_transfer_mod(req: TransferModRequest):
    repacked_file = req.repacked_path
    # Fallback to local repacked_dir if transferred from another PC or workspace directory changed
    if not repacked_file or not os.path.exists(repacked_file):
        folder_candidate = os.path.basename(os.path.normpath(req.repacked_path or ""))
        if folder_candidate == "__data":
            folder_candidate = os.path.basename(os.path.dirname(os.path.normpath(req.repacked_path or "")))
        local_cand = os.path.join(manager.repacked_dir, folder_candidate, "__data")
        if os.path.exists(local_cand):
            repacked_file = local_cand
            req.repacked_path = local_cand

    if os.path.isdir(repacked_file):
        repacked_file = os.path.join(repacked_file, "__data")
    if not os.path.exists(repacked_file) or os.path.getsize(repacked_file) == 0:
        return {"success": False, "error": f"Repacked bundle file not found or empty: {req.repacked_path}. Please re-prepare the mod."}

    loop = asyncio.get_event_loop()
    with track(f"Sending {req.mod_name or req.bundle_name} to the phone", "install") as t:
        push_ok, push_msg = await loop.run_in_executor(
            None,
            manager.adb.push_modded_bundle,
            req.device_id,
            repacked_file,
            req.bundle_name,
            req.bundle_hash,
            True,
            t.log
        )
        if not push_ok:
            t.fail(push_msg)
    if push_ok:
        # Auto mark installed if configured (supports multi-mod shared bundles)
        cfg = load_config()
        settings = cfg.get("settings") or {}
        if settings.get("auto_mark_installed", True):
            names_to_mark = req.mod_names or ([req.mod_name] if req.mod_name else [])
            updated = False
            for nm in names_to_mark:
                if nm and nm not in cfg.setdefault("installed_mods", []):
                    cfg["installed_mods"].append(nm)
                    updated = True
            if updated:
                save_config(cfg)
        return {"success": True, "message": push_msg, "installed_mods": cfg.get("installed_mods", [])}
    else:
        return {"success": False, "error": push_msg}


class CheckSharedBundlesRequest(BaseModel):
    mod_folders: List[str]
    installed_mod_names: Optional[List[str]] = None
    queue_mod_folders: Optional[List[str]] = None
    quality: Optional[str] = "HD"


@router.post("/api/mods/check-shared-bundles")
def check_shared_bundles_endpoint(req: CheckSharedBundlesRequest):
    """Which installed or queued mods share a game bundle with the mods about to be prepared. Uses the mod index, not a scan of every folder."""
    cfg = load_config()
    installed_names = set(req.installed_mod_names if req.installed_mod_names is not None else cfg.get("installed_mods", []))
    queue_folders = [os.path.abspath(f) for f in (req.queue_mod_folders or []) if f]

    candidate_mods = []
    seen = set()
    for record in db.mods_by_names(list(installed_names)):
        fp = os.path.abspath(record["folder_path"])
        if fp not in seen:
            seen.add(fp)
            candidate_mods.append({**record, "source": "installed"})
    for record in db.mods_by_folders(queue_folders):
        fp = os.path.abspath(record["folder_path"])
        if fp not in seen:
            seen.add(fp)
            candidate_mods.append({**record, "source": "queue"})

    # Queue folders outside the index (e.g. an extracted variant) are still inspected from disk.
    for qf_abs in queue_folders:
        if qf_abs not in seen and os.path.exists(qf_abs):
            seen.add(qf_abs)
            files = [f for f in os.listdir(qf_abs) if not f.startswith(".")]
            candidate_mods.append({"name": os.path.basename(qf_abs), "folder_path": qf_abs, "files": files, "source": "queue"})

    indexed = {os.path.abspath(r["folder_path"]): r for r in db.mods_by_folders(req.mod_folders)}
    res = manager.check_shared_bundles(req.mod_folders, candidate_mods, quality=req.quality or "HD", log_cb=lambda m: None if m.startswith(("Fetching latest", "Loading cached")) else emit_log(m, level="info"), lookup=indexed.get)  # (the first call may have to download the catalog: say so; the routine lines would repeat per mod)
    return {"status": "ok", **res}


class RestoreRequest(BaseModel):
    device_id: str
    bundle_name: str
    bundle_hash: str


@router.post("/api/restore")
def restore_backup(req: RestoreRequest):
    success, msg = manager.adb.restore_backup(req.device_id, req.bundle_name, req.bundle_hash)
    if success:
        return {"status": "success", "message": msg}
    raise HTTPException(status_code=400, detail=msg)


@router.get("/api/backups")
def list_backups(device_id: str):
    """Backups of original bundles kept on the phone (`__data.bak` next to each bundle the manager overwrote)."""
    return {"backups": manager.adb.list_backups(device_id)}


@router.post("/api/backups/delete")
def delete_backup(req: RestoreRequest):
    success, msg = manager.adb.delete_backup(req.device_id, req.bundle_name, req.bundle_hash)
    if success:
        return {"status": "success", "message": msg}
    raise HTTPException(status_code=400, detail=msg)
