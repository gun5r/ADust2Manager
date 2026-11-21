"""Tray icon for Linux desktops through D-Bus (StatusNotifierItem + dbusmenu): what KDE Plasma, GNOME with the AppIndicator extension, and
most current desktops use. The older X11 tray (pystray's Xorg backend) is not enough there: under Wayland its clicks go through a
compatibility layer that asks for permission to control input devices and then does nothing."""
import asyncio
import os
import threading
from typing import Callable, List, Tuple

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_property, method, signal
from dbus_fast.constants import PropertyAccess
from PIL import Image

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"


def _argb_pixmap(image_path: str, size: int = 64) -> List[List]:
    """The icon as the D-Bus pixmap format: width, height, bytes in ARGB32 network order."""
    image = Image.open(image_path).convert("RGBA").resize((size, size), Image.LANCZOS)
    data = bytearray()
    for r, g, b, a in image.getdata():
        data += bytes((a, r, g, b))
    return [[size, size, bytes(data)]]


class _Item(ServiceInterface):
    def __init__(self, pixmap, title: str, on_activate: Callable[[], None]):
        super().__init__("org.kde.StatusNotifierItem")
        self._pixmap, self._title, self._on_activate = pixmap, title, on_activate

    @dbus_property(access=PropertyAccess.READ)
    def Category(self) -> "s":
        return "ApplicationStatus"

    @dbus_property(access=PropertyAccess.READ)
    def Id(self) -> "s":
        return "ADust2Manager"

    @dbus_property(access=PropertyAccess.READ)
    def Title(self) -> "s":
        return self._title

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":
        return "Active"

    @dbus_property(access=PropertyAccess.READ)
    def WindowId(self) -> "i":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def IconName(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def IconPixmap(self) -> "a(iiay)":
        return self._pixmap

    @dbus_property(access=PropertyAccess.READ)
    def ItemIsMenu(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Menu(self) -> "o":
        return MENU_PATH

    @dbus_property(access=PropertyAccess.READ)
    def ToolTip(self) -> "(sa(iiay)ss)":
        return ["", [], self._title, ""]

    @method()
    def Activate(self, x: "i", y: "i"):  # left click
        self._on_activate()

    @method()
    def SecondaryActivate(self, x: "i", y: "i"):  # middle click
        self._on_activate()

    @method()
    def ContextMenu(self, x: "i", y: "i"):  # the desktop draws the menu itself from the dbusmenu below
        pass

    @method()
    def Scroll(self, delta: "i", orientation: "s"):
        pass


class _Menu(ServiceInterface):
    """A flat menu: item id N (from 1) is entries[N-1]; id 0 is the root."""

    def __init__(self, entries: List[Tuple[str, Callable[[], None]]]):
        super().__init__("com.canonical.dbusmenu")
        self._entries = entries

    @dbus_property(access=PropertyAccess.READ)
    def Version(self) -> "u":
        return 3

    @dbus_property(access=PropertyAccess.READ)
    def TextDirection(self) -> "s":
        return "ltr"

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":
        return "normal"

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "as":
        return []

    def _props(self, index: int) -> dict:
        label = self._entries[index][0]
        if not label:
            return {"type": Variant("s", "separator")}
        return {"label": Variant("s", label), "enabled": Variant("b", True), "visible": Variant("b", True)}

    @method()
    def GetLayout(self, parent_id: "i", recursion_depth: "i", property_names: "as") -> "u(ia{sv}av)":
        children = [Variant("(ia{sv}av)", [i + 1, self._props(i), []]) for i in range(len(self._entries))]
        return [1, [0, {"children-display": Variant("s", "submenu")}, children]]

    @method()
    def GetGroupProperties(self, ids: "ai", property_names: "as") -> "a(ia{sv})":
        return [[i, self._props(i - 1)] for i in ids if 1 <= i <= len(self._entries)]

    @method()
    def GetProperty(self, id: "i", name: "s") -> "v":
        props = self._props(id - 1) if 1 <= id <= len(self._entries) else {}
        return props.get(name, Variant("s", ""))

    @method()
    def Event(self, id: "i", event_id: "s", data: "v", timestamp: "u"):
        if event_id == "clicked" and 1 <= id <= len(self._entries):
            threading.Thread(target=self._entries[id - 1][1], daemon=True).start()  # never block the bus loop with the action

    @method()
    def EventGroup(self, events: "a(isvu)") -> "ai":
        for id, event_id, data, timestamp in events:
            self.Event(id, event_id, data, timestamp)
        return []

    @method()
    def AboutToShow(self, id: "i") -> "b":
        return False

    @method()
    def AboutToShowGroup(self, ids: "ai") -> "aiai":
        return [[], []]

    @signal()
    def LayoutUpdated(self, revision: "u", parent: "i") -> "ui":
        return [revision, parent]


class SniTray:
    """The icon, living on its own thread with its own event loop. `start` raises when there is no tray host on the session bus."""

    def __init__(self, icon_path: str, title: str, entries: List[Tuple[str, Callable[[], None]]], on_activate: Callable[[], None]):
        self._loop = asyncio.new_event_loop()
        self._bus = None
        self._ready = threading.Event()
        self._error = None
        self._args = (icon_path, title, entries, on_activate)
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)

    def start(self, timeout: float = 8.0) -> "SniTray":
        self._thread.start()
        if not self._ready.wait(timeout) or self._error:
            raise RuntimeError(self._error or "the tray host did not answer")
        return self

    def stop(self) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self._close(), self._loop).result(2)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._setup())
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            self._ready.set()
            return
        self._ready.set()
        self._loop.run_forever()

    async def _setup(self) -> None:
        icon_path, title, entries, on_activate = self._args
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus.export(ITEM_PATH, _Item(_argb_pixmap(icon_path), title, on_activate))
        self._bus.export(MENU_PATH, _Menu(entries))
        name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        await self._bus.request_name(name)
        introspection = await self._bus.introspect("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
        watcher = self._bus.get_proxy_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", introspection)
        await watcher.get_interface("org.kde.StatusNotifierWatcher").call_register_status_notifier_item(name)

    async def _close(self) -> None:
        if self._bus:
            self._bus.disconnect()
