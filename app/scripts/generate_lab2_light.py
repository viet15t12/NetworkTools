import sys
from pathlib import Path
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from docshots.environment import configure_qt_environment
configure_qt_environment()

from docshots.runtime import FixtureBundle, RenderRequest, _application, capture_window, DocshotError
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtQuick import QQuickWindow

def main():
    out_dir = APP_DIR.parent / "reports/contents/diagrams/Chuong_5_lab2"
    req = RenderRequest(width=1600, height=1000, scale=1.0, theme="light", output_dir=out_dir)
    app = _application()
    
    with FixtureBundle(req) as fixture:
        print("Database path:", fixture.device_db)
        
        # We need to populate devices
        for i in range(1, 10):
            host = f"192.168.122.10{i}"
            name = f"R{i}" if i <=6 else f"SW{i}"
            if i == 4: name = "ISP1"
            if i == 5: name = "ISP2"
            if i == 6: name = "R6"
            fixture.db_manager.addDevice(host, name, "SSH", "22", "admin", "admin", "cisco_ios", "rou", "")
            fixture.db_manager.updateDeviceConnectionStatus(host, "connected")
            
        # We need to test if we can render the main window
        engine = QQmlApplicationEngine()
        from app_facade import QML_MODULE_DIR
        engine.addImportPath(str(QML_MODULE_DIR.parent))
        
        ctx = engine.rootContext()
        for k, v in fixture.context_properties().items():
            ctx.setContextProperty(k, v)
            
        engine.loadFromModule("UI", "Main")
        roots = engine.rootObjects()
        if not roots:
            print("Failed to load QML")
            return 1
            
        window = roots[-1]
        
        # Test capture
        img = capture_window(window, 1.0)
        img.save(str(out_dir / "test.png"))
        print("Saved test.png")
        
if __name__ == "__main__":
    main()
