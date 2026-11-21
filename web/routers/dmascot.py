import os
import shutil
import subprocess
import sys
import threading
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from paths import FROZEN
from web.state import BASE_DIR
from web import state
from dmascot_manager import dmascot_mgr

router = APIRouter()


class DMascotLaunchRequest(BaseModel):
    mod_name: str
    folder_path: str
    asset_stem: Optional[str] = ""
    category: Optional[str] = "idle"
    character: Optional[str] = "Others"
    is_multi: Optional[bool] = False
    variant_path: Optional[str] = ""


class DMascotUpdateRequest(BaseModel):
    draggable: Optional[bool] = None
    locked: Optional[bool] = None
    click_through: Optional[bool] = None
    layer: Optional[str] = None
    scale: Optional[float] = None
    opacity: Optional[float] = None
    framing_mode: Optional[bool] = None
    pan_x: Optional[float] = None
    pan_y: Optional[float] = None
    char_zoom: Optional[float] = None
    anim_action: Optional[str] = None
    anim_trigger: Optional[float] = None
    aspect: Optional[str] = None
    current_animation: Optional[str] = None
    custom_w: Optional[int] = None
    custom_h: Optional[int] = None


class DMascotCtlRequest(BaseModel):
    action: str
    id: Optional[str] = None


@router.post("/api/dmascot/ctl")
def ctl_dmascot(req: DMascotCtlRequest):
    active = [m for m in dmascot_mgr.get_all() if m.get("status") == "running"]
    if not active:
        return {"status": "error", "message": "No running mascots found"}

    target = None
    if req.id:
        target = dmascot_mgr.get(req.id)
    if not target:
        target = active[-1]

    mid = target["id"]
    if req.action == "toggle_click_through":
        new_val = not target.get("click_through", False)
        dmascot_mgr.update(mid, {"click_through": new_val})
        return {"status": "ok", "action": req.action, "click_through": new_val}
    elif req.action == "toggle_framing":
        new_val = not target.get("framing_mode", False)
        dmascot_mgr.update(mid, {"framing_mode": new_val})
        return {"status": "ok", "action": req.action, "framing_mode": new_val}
    elif req.action in ("next_anim", "prev_anim", "play_motion", "motion"):
        import time
        dmascot_mgr.update(mid, {"anim_action": req.action, "anim_trigger": time.time()})
        return {"status": "ok", "action": req.action}
    elif req.action == "close":
        dmascot_mgr.close(mid)
        return {"status": "ok", "action": req.action}
    return {"status": "error", "message": f"Unknown action: {req.action}"}


@router.post("/api/dmascot/launch")
async def launch_dmascot(req: DMascotLaunchRequest):
    if FROZEN:  # the mascot windows are separate Python (Qt) processes
        raise HTTPException(status_code=400, detail="Desktop mascots are only available when the manager runs from source (python run.py).")
    dmascot_mgr.port = state.CURRENT_PORT
    mascot = dmascot_mgr.launch(req.dict())
    return {"status": "success", "mascot": mascot}


@router.get("/api/dmascot/list")
async def list_dmascots():
    return {"mascots": dmascot_mgr.get_all()}


@router.get("/api/dmascot/info/{mid}")
async def get_dmascot_info(mid: str):
    mascot = dmascot_mgr.get(mid)
    if not mascot:
        raise HTTPException(status_code=404, detail="Mascot not found")
    
    folder = mascot.get("folder_path")
    files = list(mascot.get("files") or [])
    if not files and folder and os.path.exists(folder):
        files = [f for f in os.listdir(folder) if not f.startswith(".")]
    
    mod_info = {
        "name": mascot.get("mod_name"),
        "folder_path": folder,
        "files": files,
        "asset_stem": mascot.get("asset_stem"),
        "default_animation": mascot.get("default_animation") or "idle"
    }
    return {"mascot": mascot, "mod": mod_info}


@router.post("/api/dmascot/update/{mid}")
async def update_dmascot(mid: str, req: DMascotUpdateRequest):
    patch = {k: v for k, v in req.dict().items() if v is not None}
    updated = dmascot_mgr.update(mid, patch)
    if not updated:
        raise HTTPException(status_code=404, detail="Mascot not found")
    return {"status": "success", "mascot": updated}


@router.post("/api/dmascot/close/{mid}")
async def close_dmascot(mid: str):
    success = dmascot_mgr.close(mid)
    return {"status": "success" if success else "not_found"}


@router.post("/api/dmascot/close-all")
async def close_all_dmascots():
    dmascot_mgr.close_all()
    return {"status": "success"}


@router.post("/api/dmascot/reset")
async def reset_dmascots_endpoint():
    dmascot_mgr.close_all()
    dmascot_mgr.kill_all_zombies()
    return {"status": "ok", "message": "All active and lingering mascot processes terminated."}


@router.post("/api/dmascot/install-pyside6")
async def install_pyside6_endpoint():
    import threading
    def worker():
        log_path = os.path.join(BASE_DIR, "work", "dmascot.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Manual PySide6 install triggered via API...\n")
            subprocess.run([sys.executable, "-m", "pip", "install", "PySide6", "--timeout", "120"], stdout=f, stderr=f)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return {"status": "started", "message": "PySide6 installation started in background"}


@router.post("/api/dmascot/install-kwin-rule")
async def install_kwin_rule_endpoint():
    ok, msg = dmascot_mgr.install_kwin_window_rule()
    return {"status": "ok" if ok else "error", "message": msg}


@router.get("/api/dmascot/diagnostics")
async def dmascot_diagnostics():
    log_path = os.path.join(BASE_DIR, "work", "dmascot.log")
    logs = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                logs = f.read()[-3000:]
        except Exception:
            pass

    has_pyside6 = False
    try:
        import PySide6.QtWebEngineWidgets
        has_pyside6 = True
    except Exception:
        pass

    has_pyqt6 = False
    try:
        import PyQt6.QtWebEngineWidgets
        has_pyqt6 = True
    except Exception:
        pass

    browsers = {b: bool(shutil.which(b)) for b in ["google-chrome", "google-chrome-stable", "chromium", "brave-browser", "microsoft-edge", "firefox"]}
    return {
        "python": sys.version,
        "has_pyside6": has_pyside6,
        "has_pyqt6": has_pyqt6,
        "browsers": browsers,
        "recent_logs": logs
    }
