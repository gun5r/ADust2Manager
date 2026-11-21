#!/usr/bin/env python3
"""
Standalone Desktop Mascot Window Launcher for ADust2Manager.
Supports Linux (KDE Plasma 6 / KWin on Wayland) and Windows.
Executes native Qt6/PySide6 window if available, with robust multi-browser Wayland fallback.
"""
import os
import sys
import time
import subprocess
import shutil
import webbrowser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "work", "dmascot.log")

def log(msg: str):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[DMascot] {msg}", file=sys.stderr)

def find_system_python():
    candidates = [sys.executable, "/usr/bin/python3", "/usr/bin/python3.12", "/usr/bin/python3.11", "/usr/bin/python"]
    if sys.platform == "win32":
        candidates.extend(["python.exe", "python3.exe"])
    for py in candidates:
        if (os.path.isabs(py) and os.path.exists(py)) or shutil.which(py):
            py_bin = py if os.path.isabs(py) else shutil.which(py)
            # Check if this python has PySide6 or PyQt6
            try:
                res = subprocess.run([py_bin, "-c", "import PySide6.QtWebEngineWidgets"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return py_bin, "PySide6"
            except Exception:
                pass
            try:
                res = subprocess.run([py_bin, "-c", "import PyQt6.QtWebEngineWidgets"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return py_bin, "PyQt6"
            except Exception:
                pass
    return None, None

def find_system_browsers():
    candidates = [
        "google-chrome-stable",
        "google-chrome",
        "/usr/bin/google-chrome",
        "chromium",
        "chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/chromium",
        "brave-browser",
        "/snap/bin/brave",
        "microsoft-edge-stable",
        "microsoft-edge",
        "/usr/bin/microsoft-edge",
        "firefox",
        "/snap/bin/firefox",
        "/usr/bin/firefox",
        "zen-browser",
        "msedge",
        "chrome",
        "brave"
    ]
    # Add common Windows installation paths
    if sys.platform == "win32":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pfx86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local_app = os.environ.get("LOCALAPPDATA", "")
        win_candidates = [
            os.path.join(pfx86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_app, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(local_app, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(pf, "Mozilla Firefox", "firefox.exe"),
        ]
        candidates.extend(win_candidates)

    found = []
    for c in candidates:
        if os.path.isabs(c):
            if os.path.exists(c):
                found.append(c)
        else:
            w = shutil.which(c)
            if w and w not in found:
                found.append(w)
    return found

def run_mascot(mascot_id: str, url: str):
    log(f"Starting mascot launch for ID: {mascot_id} (Platform: {sys.platform})")

    # Step 1: Check for native Qt (PySide6 / PyQt6)
    py_path, qt_flavor = find_system_python()
    if py_path and qt_flavor:
        log(f"Found native {qt_flavor} in {py_path}! Launching native Qt window...")
        qt_script = os.path.join(BASE_DIR, "core", "dmascot_qt_window.py")
        env = os.environ.copy()
        if sys.platform.startswith("linux"):
            env["QT_QPA_PLATFORM"] = "wayland;xcb"
        p = subprocess.Popen([py_path, qt_script, mascot_id, url], env=env)
        p.wait()
        return

    # Step 2: Attempt background PySide6 pip install if in venv
    log("PySide6 not found. Attempting fast pip install in background...")
    try:
        pip_res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "PySide6", "--timeout", "30", "--quiet"],
            capture_output=True,
            timeout=35
        )
        if pip_res.returncode == 0:
            log("PySide6 installed successfully! Retrying native Qt window...")
            qt_script = os.path.join(BASE_DIR, "core", "dmascot_qt_window.py")
            env = os.environ.copy()
            if sys.platform.startswith("linux"):
                env["QT_QPA_PLATFORM"] = "wayland;xcb"
            p = subprocess.Popen([sys.executable, qt_script, mascot_id, url], env=env)
            p.wait()
            return
    except Exception as e:
        log(f"Pip install attempt note: {e}")

    # Step 3: Launch via native browser window
    browsers = find_system_browsers()
    log(f"Available system browsers: {browsers}")

    user_data = os.path.join(os.path.expanduser("~"), ".bd2_mascot_profiles", mascot_id)
    os.makedirs(user_data, exist_ok=True)

    for b in browsers:
        b_lower = b.lower()
        if any(c in b_lower for c in ["chrome", "chromium", "brave", "edge", "msedge"]):
            log(f"Launching standalone container with Chromium-based browser: {b}")
            cmd = [
                b,
                f"--app={url}",
                f"--user-data-dir={user_data}",
                f"--class=BD2_Mascot",
                "--window-size=480,700",
                "--disable-gpu-vsync",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            if sys.platform.startswith("linux"):
                cmd.extend([
                    "--ozone-platform-hint=auto",
                    "--enable-features=WaylandWindowDecorations",
                    "--enable-transparent-visuals"
                ])
            try:
                proc = subprocess.Popen(cmd)
                proc.wait()
                return
            except Exception as ex:
                log(f"Failed to launch with {b}: {ex}")

    # Fallback for Firefox
    for b in browsers:
        if "firefox" in b.lower():
            log(f"Launching standalone window with Firefox: {b}")
            cmd = [b, "--new-window", url]
            try:
                proc = subprocess.Popen(cmd)
                proc.wait()
                return
            except Exception as ex:
                log(f"Failed to launch with Firefox: {ex}")

    # Universal fallback
    log("All direct browser launchers failed. Fallback to system default browser...")
    try:
        if sys.platform.startswith("linux") and shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", url])
        else:
            webbrowser.open(url)
    except Exception as ex:
        log(f"Universal browser fallback error: {ex}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        log("Usage: dmascot_window.py <mascot_id> <url>")
        sys.exit(1)
    run_mascot(sys.argv[1], sys.argv[2])
