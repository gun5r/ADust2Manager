#!/usr/bin/env python3
"""
Native Qt6 Desktop Mascot Window for ADust2Manager.
Designed for Linux (KDE Plasma 6 / KWin on Wayland & X11).
Matches KWin Window Rules (LyricsHUD pattern) with true frameless transparency,
dynamic box scaling to prevent cut-offs, and native click-through support.
"""
import os
import sys
import json
import time

os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
os.environ["MANGOHUD"] = "0"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-vulkan --disable-features=Vulkan --enable-gpu-rasterization --ignore-gpu-blocklist --enable-transparent-visuals"

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
    from PySide6.QtCore import Qt, QUrl, QTimer, QPoint
    from PySide6.QtGui import QColor, QRegion
    QT_FLAVOR = "PySide6"
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
        from PyQt6.QtCore import Qt, QUrl, QTimer, QPoint
        from PyQt6.QtGui import QColor, QRegion
        QT_FLAVOR = "PyQt6"
    except ImportError:
        print("[DMascot-Qt] Neither PySide6 nor PyQt6 is available.", file=sys.stderr)
        sys.exit(2)

class MascotWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS] {message} ({sourceID}:{lineNumber})", file=sys.stderr)

class MascotNativeWindow(QMainWindow):
    def __init__(self, mascot_id: str, url: str):
        super().__init__()
        self.mascot_id = mascot_id
        self.url = url
        self.drag_position = None
        self.current_state = {}
        self.current_scale = 1.0

        # Predictable window title and class matching KWin Window Rules
        self.setWindowTitle("BD2_Mascot")
        self.setObjectName("BD2_Mascot")

        # 1. Enable True RGBA Translucent Background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        # 2. Window Flags (Matching LyricsHUD proven pattern: Window + Frameless + StaysOnTop + DoesNotAcceptFocus)
        self.apply_window_flags(click_through=False)

        # 3. WebEngine View setup with transparent background and hardware WebGL
        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        page = MascotWebPage(self.view)
        page.setBackgroundColor(QColor(0, 0, 0, 0))
        page.geometryChangeRequested.connect(lambda geom: self.resize(geom.width(), geom.height()))
        self.view.setPage(page)
        self.view.setStyleSheet("background: transparent;")

        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        self.view.load(QUrl(url))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        container.setStyleSheet("background: transparent;")
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.resize(480, 720)

        # Polling timer for status sync with backend
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.sync_state)
        self.poll_timer.start(500)
        self.sync_state()

    def apply_window_flags(self, click_through: bool = False):
        flags = (
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setMask(QRegion())
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.clearMask()

        self.setWindowFlags(flags)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.current_state.get("locked", False):
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            if not self.current_state.get("locked", False):
                self.move(event.globalPosition().toPoint() - self.drag_position)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def sync_state(self):
        import urllib.request
        api_url = f"http://127.0.0.1:8082/api/dmascot/info/{self.mascot_id}"
        try:
            req = urllib.request.Request(api_url)
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                state = data.get("mascot") or {}
                if state.get("status") in ("closed", "stopped"):
                    self.close()
                    QApplication.quit()
                    return

                # Stable Window Sizing: maintain dimensions across animation changes
                if state.get("custom_w") and state.get("custom_h"):
                    base_w = int(state["custom_w"])
                    base_h = int(state["custom_h"])
                else:
                    aspect = state.get("aspect") or getattr(self, "_base_aspect", None)
                    if not aspect:
                        default_anim = str(state.get("default_animation") or "").lower()
                        aspect = "portrait" if ("idle" in default_anim or not default_anim) else "square"
                        self._base_aspect = aspect
                    else:
                        self._base_aspect = aspect
                    base_w, base_h = (680, 680) if aspect == "square" else (480, 720)

                new_scale = float(state.get("scale", 1.0))
                self.current_scale = new_scale
                target_w = max(260, min(2000, int(base_w * new_scale)))
                target_h = max(260, min(2000, int(base_h * new_scale)))
                if abs(target_w - self.width()) > 5 or abs(target_h - self.height()) > 5:
                    self.resize(target_w, target_h)

                # Layer changes (above vs below)
                new_layer = state.get("layer", "above")
                old_layer = self.current_state.get("layer", "above")
                if new_layer != old_layer:
                    if new_layer == "below":
                        self.setWindowFlags((self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint) | Qt.WindowType.WindowStaysOnBottomHint)
                    else:
                        self.setWindowFlags((self.windowFlags() & ~Qt.WindowType.WindowStaysOnBottomHint) | Qt.WindowType.WindowStaysOnTopHint)
                    self.show()

                # Click-Through (Game Mode)
                click_through = bool(state.get("click_through", False))
                old_click_through = bool(self.current_state.get("click_through", False))
                if click_through != old_click_through:
                    self.apply_window_flags(click_through=click_through)
                    self.show()

                self.current_state = state
        except urllib.error.HTTPError as he:
            if he.code == 404:
                # Mascot was removed or closed on server: terminate window cleanly
                self.poll_timer.stop()
                self.close()
                QApplication.quit()
                sys.exit(0)
        except Exception:
            pass

def main():
    if len(sys.argv) < 3:
        sys.exit(1)
    m_id = sys.argv[1]
    m_url = sys.argv[2]

    import signal
    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.quit())

    app = QApplication(sys.argv)

    # Heartbeat timer to allow clean Ctrl+C SIGINT handling (from LyricsHUD)
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(300)

    win = MascotNativeWindow(m_id, m_url)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
