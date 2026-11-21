"""The notification-area (system tray) icon: open the manager in the browser, quit.

Without it the packaged program has no window at all, so there would be nothing to close it with. If the platform has no tray
(no desktop session, a Linux desktop without tray support) the manager still runs; the page's power button quits it then."""
import os
import sys
import webbrowser
from typing import Callable, Optional

from paths import STATIC_DIR


def start(url: str, quit_program: Callable[[], None]) -> Optional[object]:
    """Show the icon (in its own thread); returns it, or None when the platform cannot show one."""
    if sys.platform.startswith("linux"):
        try:  # StatusNotifierItem over D-Bus first (KDE, GNOME with the AppIndicator extension...)
            import tray_sni
            icon = tray_sni.SniTray(
                os.path.join(STATIC_DIR, "icon.png"), "ADust2Manager",
                [("Open ADust2Manager", lambda: webbrowser.open(url)), ("", lambda: None), ("Quit", quit_program)],
                lambda: webbrowser.open(url),
            ).start()
            print("Tray icon started (StatusNotifierItem over D-Bus).")
            return icon
        except Exception as e:
            print(f"No D-Bus tray ({type(e).__name__}: {e}); trying the X11 tray.")
    try:
        import pystray
        from PIL import Image

        menu = pystray.Menu(
            pystray.MenuItem("Open ADust2Manager", lambda: webbrowser.open(url), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: quit_program()),
        )
        icon = pystray.Icon("ADust2Manager", Image.open(os.path.join(STATIC_DIR, "icon.png")), "ADust2Manager", menu)
        icon.run_detached()
        print(f"Tray icon started ({type(icon).__module__}).")
        return icon
    except Exception as e:  # no display, no tray support, missing backend...
        print(f"No tray icon ({type(e).__name__}: {e}); use the power button in the page to quit.")
        return None
