#!/usr/bin/env python3
"""Starts ADust2Manager: from source (`python run.py [port]`) or as the packaged program (double-click)."""
import multiprocessing
import os
import runpy
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "core"))
sys.path.insert(0, os.path.join(BASE_DIR, "web"))

FIXED_PORT = 8082


def run_helper(module: str, args: list) -> None:
    """`ADust2Manager --helper <module> args...`: the packaged program has no Python, so its helper processes are itself."""
    sys.argv = [module] + args
    runpy.run_module(module, run_name="__main__")


def main() -> None:
    import shutil
    import socket
    import threading
    import time
    import webbrowser
    import requests

    import applog
    import paths
    from spine_player import ensure

    if len(sys.argv) > 1 and not sys.argv[1].isdigit():
        print(f"Unknown option {sys.argv[1]}; usage: ADust2Manager [port]")
        return

    port = int(sys.argv[1]) if len(sys.argv) > 1 else FIXED_PORT
    url = f"http://127.0.0.1:{port}"

    try:  # already running: just show it
        if requests.get(f"{url}/api/ping", timeout=2).json().get("app") == "ADust2Manager":
            webbrowser.open(url)
            return
    except Exception:
        pass
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"Port {port} is used by another program; close it and start again.")
            return

    applog.start(os.path.join(paths.DATA_DIR, "manager.log"), paths)  # (after the check above, so a second launch leaves the log alone)
    for name in os.listdir(paths.TEMP_DIR):  # leftovers of a run that was killed
        leftover = os.path.join(paths.TEMP_DIR, name)
        shutil.rmtree(leftover, ignore_errors=True) if os.path.isdir(leftover) else os.remove(leftover)
    ensure(paths.LIBS_DIR)

    print("\n" + "═" * 65)
    print("  ADust2Manager - mod manager for Brown Dust 2")
    print("═" * 65)
    print(f"  • Web Dashboard URL : {url}")
    print(f"  • Data folder       : {paths.DATA_DIR}")
    print("═" * 65 + "\n")

    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    from web.app import request_quit, run_server
    import tray
    icon = tray.start(url, request_quit)
    code = 0
    try:
        run_server(port)
    except SystemExit as e:  # uvicorn exits this way when it cannot start (port taken...)
        code = e.code if isinstance(e.code, int) else 1
    except BaseException:
        import traceback
        print("The server stopped with an error:\n" + traceback.format_exc())
        code = 1
    finally:
        shutdown(icon)
    os._exit(code)  # nothing may keep the process (and so a ghost) alive after this point


def shutdown(icon) -> None:
    """Remove the tray icon and stop the worker processes; every step is allowed to fail."""
    print("Shutting down.")
    if icon:  # stop() can wait several seconds for the tray thread; the process ends right after anyway
        import threading
        stopper = threading.Thread(target=icon.stop, daemon=True)
        stopper.start()
        stopper.join(1.5)
    try:
        for p in multiprocessing.active_children():
            p.terminate()
        from web.state import manager
        manager.adb.stop_server_if_started()
    except Exception as e:
        print(f"(while shutting down: {e})")
    sys.stdout.flush()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # the texture workers are processes: needed once packaged
    if len(sys.argv) > 2 and sys.argv[1] == "--helper":
        run_helper(sys.argv[2], sys.argv[3:])
    else:
        try:
            main()
        except Exception:
            import traceback
            text = traceback.format_exc()
            print("The manager failed to start:\n" + text)
            try:
                import paths
                with open(os.path.join(paths.DATA_DIR, "manager.log"), "a", encoding="utf-8") as f:  # the log may not have started yet
                    f.write("The manager failed to start:\n" + text)
                if paths.FROZEN and os.name == "nt":  # no console to show it in
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(0, f"ADust2Manager failed to start.\n\nDetails are in:\n{os.path.join(paths.DATA_DIR, 'manager.log')}", "ADust2Manager", 0x10)
            except Exception:
                pass
            raise
