# PyInstaller spec: `pyinstaller packaging/adust2manager.spec --distpath dist-app --workpath build` (after `npm run build` in frontend/)
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
R = lambda *p: os.path.join(ROOT, *p)

datas = [(R("frontend", "dist"), "frontend/dist"), (R("web", "static"), "web/static"), (R("bin"), "bin"), (R("LICENSE"), "."), (R("THIRD_PARTY_NOTICES.md"), ".")]
binaries = []
hiddenimports = ["extract_costume_portraits", "dating_scene_export", "fmod_toolkit"]  # fmod_toolkit: UnityPy.export imports it; our stub (packaging/stubs) stands in for the real one  # started as helper processes (`run.py --helper`), never imported
hiddenimports += ["tray_sni"] + collect_submodules("dbus_fast") + collect_submodules("pystray") + collect_submodules("Xlib") + collect_submodules("uvicorn") + collect_submodules("web") + collect_submodules("core")
for package in ("UnityPy", "texture2ddecoder", "astc_encoder", "etcpak", "archspec"): 
    try:
        d, b, h = collect_all(package)
    except Exception:
        continue
    datas += d; binaries += b; hiddenimports += h

a = Analysis([R("run.py")], pathex=[R("packaging", "stubs"), R("core"), ROOT], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["tkinter", "PySide6", "PyQt6", "PyQt5", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ADust2Manager", console=False, icon=R("web", "static", "icon.png"))
coll = COLLECT(exe, a.binaries, a.datas, name="ADust2Manager")
