import os
import shutil
import subprocess
import sys
from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from paths import clean_env
from web.state import db, load_config, manager, save_config

router = APIRouter()


class ConfigModel(BaseModel):
    mods_dir: Optional[str] = None
    quality: Optional[str] = "HD"
    folder_tabs: Optional[List[dict]] = None
    active_tab_id: Optional[str] = None
    installed_mods: Optional[List[str]] = None
    templates: Optional[dict] = None
    settings: Optional[dict] = None


@router.get("/api/config")
def get_settings():
    return load_config()


@router.post("/api/config")
def update_settings(cfg: ConfigModel):
    existing = load_config()
    data = cfg.dict(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            existing[k] = v
    save_config(existing)
    return {"status": "ok", "config": existing}


@router.get("/api/devices")
def list_devices():
    devices = manager.adb.get_devices()
    for d in devices:
        if d["status"] == "device":
            d["game_installed"] = manager.adb.check_game_installed(d["id"])
        else:
            d["game_installed"] = False
    return {"devices": devices}


class ToggleInstalledRequest(BaseModel):
    mod_name: str
    installed: bool


@router.post("/api/mod/toggle-installed")
def toggle_installed(req: ToggleInstalledRequest):
    cfg = load_config()
    installed_list = cfg.setdefault("installed_mods", [])
    if req.installed:
        if req.mod_name not in installed_list:
            installed_list.append(req.mod_name)
    else:
        if req.mod_name in installed_list:
            installed_list.remove(req.mod_name)
    save_config(cfg)
    return {"status": "ok", "installed_mods": installed_list}


class SaveTabsRequest(BaseModel):
    folder_tabs: List[dict]
    active_tab_id: Optional[str] = None


@router.post("/api/tabs/save")
def save_tabs(req: SaveTabsRequest):
    cfg = load_config()
    cfg["folder_tabs"] = req.folder_tabs  # may be empty: the user can remove every folder
    if req.active_tab_id is not None:
        cfg["active_tab_id"] = req.active_tab_id
        for tab in req.folder_tabs:
            if tab.get("id") == req.active_tab_id:
                cfg["mods_dir"] = tab.get("path", cfg.get("mods_dir", ""))
                break
    save_config(cfg)
    # Mods of a removed (or re-pointed) folder must not linger in the library index.
    roots = [os.path.abspath(os.path.expanduser(t["path"])) for t in cfg.get("folder_tabs", []) if t.get("path")]
    db.prune_roots(roots)
    return {"status": "ok", "config": cfg}


@router.get("/api/folders/check")
def check_folder(path: str):
    """Does this folder exist and can it be read? (Used by the folder-tab editor before saving.)"""
    target = os.path.abspath(os.path.expanduser(path.strip()))
    is_dir = os.path.isdir(target)
    return {"path": target, "exists": os.path.exists(target), "is_dir": is_dir, "readable": is_dir and os.access(target, os.R_OK | os.X_OK)}


class SaveTemplateRequest(BaseModel):
    tab_id: str
    template_name: str
    mod_names: List[str]


@router.post("/api/templates/save")
def save_template(req: SaveTemplateRequest):
    cfg = load_config()
    templates = cfg.setdefault("templates", {})
    tab_templates = templates.setdefault(req.tab_id, {})
    tab_templates[req.template_name] = req.mod_names
    save_config(cfg)
    return {"status": "ok", "templates": templates}


class DeleteTemplateRequest(BaseModel):
    tab_id: str
    template_name: str


@router.post("/api/templates/delete")
def delete_template(req: DeleteTemplateRequest):
    cfg = load_config()
    templates = cfg.setdefault("templates", {})
    if req.tab_id in templates and req.template_name in templates[req.tab_id]:
        del templates[req.tab_id][req.template_name]
        save_config(cfg)
    return {"status": "ok", "templates": templates}


def _configured_roots() -> List[str]:
    return [os.path.realpath(os.path.expanduser(t["path"])) for t in load_config().get("folder_tabs", []) if t.get("path")]


class OpenFolderRequest(BaseModel):
    path: str


@router.post("/api/folders/open")
def open_folder(req: OpenFolderRequest):
    """Show a folder in the system's file manager. Only a folder tab (or something inside one) can be opened: this is no way to launch arbitrary paths."""
    target = os.path.realpath(os.path.expanduser(req.path.strip()))
    if not any(target == root or target.startswith(root.rstrip(os.sep) + os.sep) for root in _configured_roots()):
        raise HTTPException(status_code=403, detail="That folder is not one of your folder tabs")
    if not os.path.isdir(target):
        raise HTTPException(status_code=404, detail="The folder does not exist (any more)")
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target], env=clean_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"status": "ok"}


def _windows_folder_dialog(start: str) -> Optional[str]:
    """The Explorer folder window (SHBrowseForFolder), shown on top of the browser. None when cancelled."""
    import ctypes
    from ctypes import wintypes

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [("hwndOwner", wintypes.HWND), ("pidlRoot", ctypes.c_void_p), ("pszDisplayName", ctypes.c_void_p),
                    ("lpszTitle", wintypes.LPCWSTR), ("ulFlags", wintypes.UINT), ("lpfn", ctypes.c_void_p),
                    ("lParam", wintypes.LPARAM), ("iImage", ctypes.c_int)]

    shell, ole = ctypes.windll.shell32, ctypes.windll.ole32
    shell.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFO)]
    shell.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    BIF_RETURNONLYFSDIRS, BIF_NEWDIALOGSTYLE = 0x1, 0x40
    ole.OleInitialize(None)
    try:
        name_buffer = ctypes.create_unicode_buffer(260)
        info = BROWSEINFO(ctypes.windll.user32.GetForegroundWindow(), None, ctypes.addressof(name_buffer), "Choose the folder",
                          BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE, None, 0, 0)
        pidl = shell.SHBrowseForFolderW(ctypes.byref(info))
        if not pidl:
            return None
        buffer = ctypes.create_unicode_buffer(32768)
        ok = shell.SHGetPathFromIDListW(pidl, buffer)
        ole.CoTaskMemFree(pidl)
        return buffer.value if ok else None
    finally:
        ole.OleUninitialize()


def _linux_folder_dialog(start: str) -> Optional[str]:
    """kdialog (KDE) or zenity (GNOME and others), whichever is installed. None when cancelled; RuntimeError when neither exists."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    tools = {"kdialog": ["kdialog", "--getexistingdirectory", start], "zenity": ["zenity", "--file-selection", "--directory", f"--filename={start.rstrip('/')}/"]}
    for name in (["kdialog", "zenity"] if "KDE" in desktop else ["zenity", "kdialog"]):
        if shutil.which(name):
            done = subprocess.run(tools[name], capture_output=True, text=True, env=clean_env())
            if done.returncode == 0:
                return done.stdout.strip() or None
            if done.returncode == 1:  # cancelled
                return None
            raise RuntimeError(done.stderr.strip() or f"{name} failed")
    raise RuntimeError("Neither kdialog nor zenity is installed")


class PickFolderRequest(BaseModel):
    start: str = ""


@router.post("/api/folders/pick")
def pick_folder(req: PickFolderRequest):
    """Show the computer's own folder window and return the chosen path ({"path": null} when cancelled). A web page cannot read the path
    of the browser's own dialogs, so the manager opens this one itself, whichever browser is used."""
    start = os.path.expanduser(req.start.strip() or "~")
    start = start if os.path.isdir(start) else os.path.expanduser("~")
    try:
        path = _windows_folder_dialog(start) if os.name == "nt" else _linux_folder_dialog(start)
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"The folder window could not be opened: {e}")
    return {"path": os.path.abspath(path) if path else None}
