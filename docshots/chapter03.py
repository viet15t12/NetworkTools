"""Chapter 3 orientation shots, driven through production QML actions.

Only data/session backends are fixtures. Crops are native-resolution rectangles
of the composed Qt framebuffer, never resized or reconstructed UI.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QObject, QPointF
from . import runtime as rt
from .shots import CHAPTER_03_FILENAMES, ShotSpec


def render_chapter_03_workflow(request: rt.RenderRequest) -> tuple[rt.RenderResult, ...]:
    if request.width < 1600 or request.height < 1000 or request.scale <= 0:
        raise rt.DocshotError("Chapter 3 requires at least a 1600x1000 logical window.")
    app = rt._application()
    request.output_dir.parent.mkdir(parents=True, exist_ok=True)
    engine = window = None
    results = []
    # Fail closed if a future backend accidentally attempts network/process I/O.
    with patch("socket.socket.connect", side_effect=rt.DocshotError("Network forbidden in docshots")), \
         patch("socket.socket.connect_ex", side_effect=rt.DocshotError("Network forbidden in docshots")), \
         patch("subprocess.Popen", side_effect=rt.DocshotError("External processes forbidden in docshots")), \
         tempfile.TemporaryDirectory(prefix=".chapter03-", dir=request.output_dir.parent) as temporary, \
         rt.FixtureBundle(request) as fixture:
        staging = Path(temporary)
        try:
            engine, window = rt._load_prepared_window(
                fixture, "Main", ShotSpec("chapter-03", "Main", "CAMS Interface Lab", "192.0.2.1"), request
            )

            def item(name):
                found = window.findChild(QObject, name)
                if found is None:
                    raise rt.DocshotError(f"Missing production component: {name}")
                return found

            sidebar = item("mainPanelSideBar")
            tabs = item("mainDeviceTabs")
            features = item("mainFeatureBar")
            content = item("mainContentArea")
            activity = item("mainActivityBar")
            registry = item("appCommandRegistry")
            menu = item("modernMenuBar")
            status = item("mainStatusBar")
            item("disconnectedDeviceGroup").setProperty("expanded", True)

            def require(condition, message):
                if not condition:
                    raise rt.DocshotError(message)

            def settle():
                rt._wait_until(app, lambda: not content.property("activeViewLoading")
                               and not sidebar.property("pythonDepsChecking")
                               and sidebar.property("pythonDepsStatus") == "success",
                               request.timeout_ms, "ready content and runtime")
                rt._wait_for_stable_scene(app, engine, window, request.timeout_ms)

            def origin(component):
                return component.mapToItem(window.contentItem(), QPointF(0, 0))

            def save(filename, rect=None):
                settle()
                image = rt.capture_window(window, request.scale, request.timeout_ms)
                if rect:
                    x, y, width, height = rect
                    require(x >= 0 and y >= 0 and x + width <= window.width()
                            and y + height <= window.height(), "Crop outside production window")
                    image = image.copy(round(x * request.scale), round(y * request.scale),
                                       round(width * request.scale), round(height * request.scale))
                path = staging / filename
                rt._save_png_atomic(image, path)
                rt._validate_saved_png(path, image.size())
                results.append(rt.RenderResult(path, image.width(), image.height()))

            def activate(host):
                sidebar.activateDevice(host)
                settle()
                require(tabs.property("activeUid") == host and sidebar.property("activeHost") == host,
                        "Tab and sidebar host context differ")

            def labels():
                return [entry["label"] for entry in rt._to_python(features.property("textFeatures"))
                        if entry["implemented"]]

            activate("192.0.2.11")
            activate("192.0.2.1")
            activate("192.0.2.11")
            activate("192.0.2.1")
            require(tabs.property("tabCount") == 2, "Reopening a host created a duplicate tab")
            require(labels() == ["Routing", "DHCP", "ACL", "NAT", "FHRP", "Syslog Server"],
                    "Router feature mapping changed")
            save(CHAPTER_03_FILENAMES[0])
            require(menu.openMenuById("view"), "View menu did not open")
            save(CHAPTER_03_FILENAMES[1], (0, 0, 348, 310))
            menu.closeAllMenus()
            save(CHAPTER_03_FILENAMES[2], (0, 0, 348, 330))
            p = origin(sidebar)
            save(CHAPTER_03_FILENAMES[3], (p.x(), p.y(), sidebar.width(), 300))
            p = origin(tabs)
            save(CHAPTER_03_FILENAMES[4], (p.x(), p.y(), 660, tabs.height() + features.height() + 14))
            save(CHAPTER_03_FILENAMES[5], (p.x(), p.y(), 620, 128))

            # The production click functions must select the correct view and
            # remember that view separately in each device tab.
            features.selectMainFeature(2)
            settle()
            require(content.property("activeMainFeatureName") == "Interface"
                    and content.property("interfaceViewLoaded"), "Interface view did not load")
            features.selectTextFeature(0)
            settle()
            require(content.property("activeFeatureName") == "Routing"
                    and content.property("routingViewLoaded"), "Routing view did not load")
            activate("192.0.2.11")
            require(labels() == ["Switching", "Security", "Monitoring", "Syslog Server"],
                    "L2 switch feature mapping changed")
            require(tabs.property("currentFMain") == 0, "SW1 did not preserve Information")
            save(CHAPTER_03_FILENAMES[6], (p.x(), p.y(), 620, 128))
            activate("192.0.2.1")
            require(tabs.property("currentFText") == 0, "R1 did not remember Routing")
            features.selectMainFeature(0)
            settle()
            require(content.property("activeMainFeatureName") == "Information"
                    and content.property("informationViewLoaded"), "Information view did not load")
            p = origin(content)
            save(CHAPTER_03_FILENAMES[7], (p.x(), p.y(), content.width(), 560))
            p = origin(status)
            save(CHAPTER_03_FILENAMES[8], (0, p.y(), window.width(), status.height()))
            save("09-status-details.png", (window.width() - 550, p.y(), 550, status.height()))

            # Real Dashboard click path toggles, unlike the menu's navigation action.
            dashboard = rt._find_visible_item(activity, "tooltipText", "Dashboard (Ctrl+Alt+D)", "Dashboard")
            rt._click_item(window, dashboard)
            settle()
            require(not window.property("sidebarVisible"), "Clicking active Dashboard did not hide sidebar")
            rt._click_item(window, dashboard)
            settle()
            require(window.property("sidebarVisible"), "Clicking active Dashboard did not restore sidebar")
            require(registry.triggerToggleSidebar(), "Sidebar command was rejected")
            settle()
            require(not window.property("sidebarVisible") and tabs.property("activeUid") == "192.0.2.1"
                    and sidebar.property("activeHost") == "192.0.2.1"
                    and tabs.property("currentFMain") == 0, "Sidebar toggle lost context")
            save(CHAPTER_03_FILENAMES[9])
            registry.triggerToggleSidebar()
            registry.triggerSettings()
            settle()
            require(activity.property("appMode") == "settings", "Settings command failed")
            registry.triggerDashboard()
            settle()
            require(activity.property("appMode") == "devices" and tabs.property("tabCount") == 2,
                    "Dashboard did not restore the device workspace")

            activate("192.0.2.13")
            require(labels() == ["Routing", "Switching", "Services", "Security", "Monitoring", "FHRP", "Syslog Server"],
                    "L3 switch feature mapping changed")
            tabs.closeCurrentTab()
            settle()
            require(tabs.property("activeUid") == "192.0.2.1"
                    and len(fixture.db_manager.getDevices()) == 4,
                    "Closing the active tab did not preserve inventory/history")

            request.output_dir.mkdir(parents=True, exist_ok=True)
            published = []
            for result in results:
                destination = request.output_dir / result.path.name
                result.path.replace(destination)
                published.append(rt.RenderResult(destination, result.width, result.height))
            return tuple(published)
        finally:
            rt._dispose_qml_window(app, engine, window)
