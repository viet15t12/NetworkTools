"""Offline Chapter 4: production QML, database/services and fake connectors only.

No UI replicas or PNG painting. Secondary windows retain production geometry.
Regenerate with scripts/docshots.py chapter-04.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from docshots import runtime as rt
from PyQt6.QtCore import QObject, QTimer, QPointF, pyqtSlot
from PyQt6.QtQml import QQmlExpression, qmlContext
from core.terminal import TerminalHelper
from features.devices import DeviceRepository, DeviceLoginService, DeviceService
from infrastructure.network.session_registry import DeviceSessionRegistry

HOSTS = ('192.168.56.11', '192.168.56.12', '192.168.56.21', '192.168.56.23')
TEMP = '192.168.56.99'
FILENAMES = (
 '01-devices-inventory.png', '02-add-device-empty.png', '03-add-device-filled.png',
 '04-device-added-waiting.png', '05-ssh-compatibility.png', '06-add-multiple-devices.png',
 '07-batch-devices-filled.png', '08-search-filter.png', '09-device-context-waiting.png',
 '10-device-connected.png', '11-device-context-connected.png', '12-device-context-disconnected.png',
 '13-multi-select.png', '14-multi-select-actions.png', '15-edit-device.png',
 '16-delete-device-confirmation.png', '17-running-config-result.png',
 '18-import-result.png', '19-batch-table-detail.png',
)

class Connector:
    """Deterministic in-memory network boundary; never creates a socket."""
    def __init__(self, device):
        self.device = device
        self.connected = False
        self.connection = self
        self.saved = False
    def connect(self):
        self.connected = True
        return True
    def disconnect(self):
        self.connected = False
    def is_alive(self):
        return self.connected
    def collect_running_config(self):
        return {'ok': True, 'running_config':
            f"hostname {self.device['device_name']}\ninterface GigabitEthernet0/0\n"
            f" ip address {self.device['host']} 255.255.255.0\n no shutdown\n", 'interface_brief': ''}
    def collect_switch_state(self):
        return {'ok': True, 'outputs': {}}
    def save_config(self, **_kwargs):
        self.saved = True
        return '[OK]'

class Terminal(rt.DocumentationTerminal):
    """Keep real services, serialize asynchronous delivery for repeatable shots."""
    def __init__(self, fixture):
        super().__init__()
        repo = DeviceRepository(fixture.device_db)
        login = DeviceLoginService(repo)
        self.sessions = DeviceSessionRegistry(login.load, connector_factory=Connector)
        self.real = TerminalHelper(
            config_backup_service=fixture.db_manager._config_backup_service,
            config_sync_service=fixture.db_manager._config_sync_service,
            session_registry=self.sessions, injected_device_service=DeviceService(repo),
            injected_login_service=login, terminal_manager=rt.DocumentationTerminal())
        self.calls = []
        self.number = 0
    @pyqtSlot(str, result=bool)
    def hasDeviceSession(self, host):
        return self.sessions.has_session(host)
    @pyqtSlot(str, result=bool)
    def connectHostAndSyncAsync(self, host):
        self.calls.append(('connect', [host]))
        def done():
            result = self.real.connectHostAndSync(host)
            require(result['ok'], result.get('message'))
            self.connectHostFinished.emit(host, True, 'Connected successfully.')
        QTimer.singleShot(0, done)
        return True
    def batch(self, operation, hosts):
        self.number += 1
        batch_id = f'chapter04-{self.number}'
        self.calls.append((operation, list(hosts)))
        def done():
            for host in hosts:
                if operation == 'connect':
                    result = self.real.connectHostAndSync(host)
                elif operation == 'running-config':
                    result = self.real.saveRunningConfigBackup(host)
                    self.runningConfigFinished.emit(host, bool(result['ok']), 'Running-config collected.')
                else:
                    result = self.closeDeviceSession(host)
                require(result['ok'], result.get('message'))
                self.hostOperationChanged.emit(batch_id, host, 'success', 'Completed', 100)
            self.batchFinished.emit(batch_id, True, {'success': len(hosts), 'failed': 0})
        QTimer.singleShot(0, done)
        return batch_id
    @pyqtSlot('QVariantList', result=str)
    def connectHostsAsync(self, hosts):
        return self.batch('connect', hosts)
    @pyqtSlot('QVariantList', result=str)
    def getRunningConfigsAsync(self, hosts):
        return self.batch('running-config', hosts)
    @pyqtSlot('QVariantList', result=str)
    def disconnectHostsAsync(self, hosts):
        return self.batch('disconnect', hosts)
    @pyqtSlot(str, result='QVariant')
    def closeDeviceSession(self, host):
        result = self.real.closeDeviceSession(host)
        self.deviceSessionClosed.emit(host)
        return result
    @pyqtSlot(str, result='QVariant')
    def pingHost(self, host):
        self.calls.append(('ping', [host]))
        return {'ok': True, 'severity': 'success', 'message': f'{host}: Reachable'}
    @pyqtSlot(str, result=bool)
    def saveDeviceConfigAsync(self, host):
        result = self.real._save_config_service.save(host)
        require(result['ok'], 'Fixture save failed')
        self.calls.append(('save', [host]))
        QTimer.singleShot(0, lambda: self.saveConfigFinished.emit(host, True, result['message']))
        return True
    @pyqtSlot(str, result=bool)
    def manualSyncAsync(self, host):
        result = self.real.manualSync(host)
        require(result['ok'], 'Fixture sync failed')
        self.calls.append(('sync', [host]))
        QTimer.singleShot(0, lambda: self.manualSyncPreviewFinished.emit(host, True, 'Preview ready', {'conflicts': []}))
        return True
    @pyqtSlot(str, str, result=bool)
    def applyManualSyncAsync(self, host, mode):
        require(self.real.applyManualSync(host, mode)['ok'], 'Sync apply failed')
        self.calls.append(('sync-' + mode, [host]))
        return True
    def shutdown(self):
        self.real.shutdown()
        super().shutdown()

class Fixture(rt.FixtureBundle):
    def _populate_devices(self):
        pass
    def _populate_vlans(self):
        pass
    def __init__(self, request):
        super().__init__(request)
        self.cli = Terminal(self)
        repository = self.db_manager._config_backup_service.repository
        commit = repository.commit_snapshot
        repository.commit_snapshot = lambda host, content, **kw: commit(host, content, timestamp=1788224400, **kw)

def require(condition, message):
    if not condition:
        raise rt.DocshotError(str(message))

def render_chapter_04_workflow(request):
    require(request.width >= 1600 and request.height >= 1000 and request.scale > 0,
            'Chapter 4 requires at least 1600x1000 logical pixels')
    # Use the native framebuffer at the requested DPI. Qt's software ancestor
    # grab loses the transparent top-level window background at synthetic scales.
    existing = rt.QApplication.instance()
    require(existing is None or abs(existing.devicePixelRatio()-request.scale)<0.001,
            'Run chapter-04 in a fresh process at its requested scale')
    if existing is None:
        os.environ['QT_SCALE_FACTOR'] = str(request.scale)
    app = rt._application()
    app.setCursorFlashTime(0)
    original_framebuffer = rt._capture_window_framebuffer
    def capture_at_dpi(item, pixel_size, timeout_ms=10000):
        ratio = item.window().devicePixelRatio()
        target = rt.QSize(round(pixel_size.width()/ratio), round(pixel_size.height()/ratio))
        grab = item.grabToImage(target)
        require(grab is not None, 'Qt component grab did not start')
        rt._wait_until(app, lambda: not grab.image().isNull(), timeout_ms, 'native DPI component')
        image = grab.image()
        require(image.size() == pixel_size, 'Native DPI component size mismatch')
        return image
    def capture_native(win, scale, timeout_ms):
        if abs(scale-win.devicePixelRatio()) < 0.001:
            image = win.grabWindow()
            require(not image.isNull(), 'Native window framebuffer is empty')
            return image
        return original_framebuffer(win, scale, timeout_ms)
    request.output_dir.parent.mkdir(parents=True, exist_ok=True)
    results = []
    engine = window = None
    with patch.object(rt, 'capture_item', capture_at_dpi), \
         patch.object(rt, '_capture_window_framebuffer', capture_native), \
         patch('socket.socket.connect', side_effect=rt.DocshotError('Network forbidden')), \
         patch('socket.socket.connect_ex', side_effect=rt.DocshotError('Network forbidden')), \
         patch('socket.socket.sendto', side_effect=rt.DocshotError('Network forbidden')), \
         patch('subprocess.Popen', side_effect=rt.DocshotError('External processes forbidden')), \
         patch('features.config_backup.repository.ConfigBackupRepository._timezone_offset', return_value=0), \
         tempfile.TemporaryDirectory(prefix='cams-chapter04-') as tempdir, \
         Fixture(request) as fixture:
        staging = Path(tempdir)
        db = fixture.db_manager
        try:
            engine, window = rt._load_prepared_window(fixture, 'Main', rt.ShotSpec('chapter-04', 'Main', 'CAMS Device Lab'), request)
            sidebar = window.findChild(QObject, 'mainPanelSideBar')
            panel = next(o for o in window.findChildren(QObject) if o.metaObject().className().startswith('DevicesPanel_'))
            def settle(win=window):
                rt._wait_for_stable_scene(app, engine, win, request.timeout_ms)
            def find(root, prop, value):
                return rt._find_visible_item(root, prop, value, str(value))
            def click(root, text, win=window):
                # Choose the interactive wrapper, not its Text child.
                matches = [o for o in rt._visual_items(root) if rt._is_visible_item(o)
                           and o.property('text') == text and (hasattr(o, 'clicked') or hasattr(o, 'triggered'))]
                require(len(matches) == 1, f'Button {text}: {len(matches)} matches')
                rt._click_item(win, matches[0])
                settle(win if win.isVisible() else window)
            def save(name, win=window, rect=None, popup=None, component=None):
                rt.QTest.mouseMove(win, rt.QPoint(win.width()-3, win.height()-3))
                settle(win)
                img = (rt.capture_popup(win, rt._popup_item_for(popup), request.scale, request.timeout_ms, 24)
                       if popup else rt.capture_window(win, request.scale, request.timeout_ms))
                if component is not None:
                    img = rt.capture_item(component, rt.QSize(round(component.width()*request.scale), round(component.height()*request.scale)), request.timeout_ms)
                # QPainter uses device-independent coordinates; flatten in physical pixels.
                img.setDevicePixelRatio(1.0)
                if img.hasAlphaChannel():
                    flattened = rt.QImage(img.size(), rt.QImage.Format.Format_RGB32)
                    flattened.fill(rt.QColor('#ffffff' if request.theme == 'light' else '#202020'))
                    painter = rt.QPainter(flattened)
                    painter.drawImage(0, 0, img)
                    painter.end()
                    img = flattened
                if rect:
                    x,y,w,h = rect
                    img = img.copy(round(x*request.scale), round(y*request.scale), round(w*request.scale), round(h*request.scale))
                path = staging / name
                rt._save_png_atomic(img, path)
                # Sparse text crops can miss the runtime's 13x17 blank-image grid.
                reader = rt.QImageReader(str(path), b'PNG')
                require(reader.canRead() and reader.size() == img.size(), 'Invalid PNG')
                colors = {img.pixelColor(x, y).rgba()
                          for y in range(0, img.height(), 3)
                          for x in range(0, img.width(), 3)}
                require(len(colors) > 8, 'Blank screenshot')
                results.append(rt.RenderResult(path, img.width(), img.height()))
            def inventory(name):
                window.setProperty('sidebarVisible', True)
                panel.expandAllDeviceGroups()
                settle()
                p = sidebar.mapToItem(window.contentItem(), QPointF(0,0))
                devices = [d for d in rt._to_python(panel.property('allDevices')) if d['ip'] in rt._to_python(panel.visibleHosts())]
                groups = len({d['status'] for d in devices})
                height = 150 + len(devices)*28 + max(0, groups-1)*28 + (42 if panel.property('multiSelectMode') else 0)
                save(name, rect=(p.x(), p.y(), sidebar.width(), height))
            def childwin(prefix):
                found = next(o for o in window.findChildren(rt.QQuickWindow) if o.metaObject().className().startswith(prefix))
                found.setColor(rt.QColor('#ffffff' if request.theme == 'light' else '#202020'))
                found.setPosition(0,0)
                settle(found)
                return found
            def field(win, label, value):
                wrapper = find(win, 'labelText', label)
                wrapper.setProperty('text', value)
                return wrapper
            def state(host):
                return next(d['status'] for d in db.getDevices() if d['ip'] == host)
            def menu(host):
                panel.handleDeviceRightClicked(host, state(host), 345, 100)
                settle()
                return next(o for o in rt._visual_items(window) if o.metaObject().className().startswith('DeviceContextMenu_'))
            def menu_shot(name, host):
                m = menu(host)
                save(name, component=m)
                return m

            panel.openNewDeviceWindow()
            new = childwin('NewDevice_')
            new.contentItem().forceActiveFocus()
            save(FILENAMES[1], new)
            protocol = next(o for o in new.findChildren(QObject) if o.metaObject().className().startswith('ProtocolComboBox_'))
            for index, port in enumerate(('22', '23', '830', '443')):
                protocol.setProperty('currentIndex', index)
                port_fields = [o for o in rt._visual_items(new) if o.property('text') == port]
                require(bool(port_fields), 'Protocol did not update default port')
            protocol.setProperty('currentIndex', 0)
            hostfield = field(new, 'Host:', '192.0.2.1')
            require(new.validate() is False, 'Public/documentation IPv4 unexpectedly accepted')
            new.handleEscapeAction()
            field(new, 'Host:', HOSTS[0]); field(new, 'Device Name:', 'R1')
            field(new, 'Username:', 'admin'); field(new, 'Password:', 'x' * 12)
            require(new.validate(), 'Private fixture host rejected')
            # Remove the blinking insertion cursor, leaving password echo mode intact.
            new.contentItem().forceActiveFocus()
            save(FILENAMES[2], new)
            click(new, 'SSH Compatibility — Legacy devices only', new)
            ssh = rt._find_dialog(new, 'SSH Compatibility')
            require(float(ssh.property('width')) <= new.width() and float(ssh.property('height')) <= new.height(), 'SSH dialog exceeds production window')
            save(FILENAMES[4], new, popup=ssh)
            ssh.close(); settle(new)
            click(new, 'Add Device', new)
            require(state(HOSTS[0]) == 'waiting', 'Add did not persist Waiting')
            require(len(rt._to_python(panel.property('allDevices'))) == 1, 'Panel did not reload added device')
            inventory(FILENAMES[3])
            require(not db.addDevice(HOSTS[0], 'Duplicate', 'SSH', '22', '', '', 'cisco_ios', 'rou', ''), 'Duplicate accepted')

            panel.openBatchDeviceWindow()
            batch = childwin('BatchNewDevice_')
            save(FILENAMES[5], batch)
            model = next(o for o in batch.findChildren(QObject) if o.metaObject().className().startswith('QQmlListModel'))
            def row_set(index, key, value):
                expr = QQmlExpression(qmlContext(model), model, f'rowModel.setProperty({index}, {json.dumps(key)}, {json.dumps(value)})')
                expr.evaluate()
                require(not expr.hasError(), expr.error().toString())
            field(batch, 'Username', 'admin')
            click(batch, 'Apply to all', batch)
            batch.initRows(3)
            batch.setProperty('formMessage', '')
            rows = []
            for host,name,role in zip(HOSTS[1:], ('R2','SW1','SW3'), ('rou','sw2','sw3')):
                rows.append({'host':host,'name':name,'protocol':'SSH','port':'22','os':'cisco_ios','role':role,'username':'admin','password':''})
            for i,row in enumerate(rows):
                for key,value in row.items():
                    row_set(i, key, value)
            batch.touchRows()
            # QML duplicate validation rejects the whole list before database writes.
            row_set(1, 'host', HOSTS[1]); batch.submitBatch()
            require(batch.property('formSeverity') == 'error' and len(db.getDevices()) == 1, 'Batch duplicate guard failed')
            row_set(1, 'host', HOSTS[2]); batch.touchRows()
            batch.contentItem().forceActiveFocus()
            save(FILENAMES[6], batch)
            save(FILENAMES[18], batch, rect=(33, 180, 397, 195))
            batch.submitBatch(); settle()
            require(len(db.getDevices()) == 4 and all(d['status']=='waiting' for d in db.getDevices()), 'Batch insert failed')
            duplicate_result = db.addDevicesBatch(rows)
            require(duplicate_result['added']==0 and duplicate_result['skipped']==3, 'Existing batch duplicates not skipped')
            inventory(FILENAMES[0])

            search = next(o for o in panel.findChildren(QObject) if o.metaObject().className().startswith('SideBarSearch_'))
            search.setProperty('text', 'SW'); panel.applyFilters()
            require(set(rt._to_python(panel.visibleHosts())) == set(HOSTS[2:]), 'Search result differs')
            inventory(FILENAMES[7])
            search.setProperty('text', ''); panel.applyFilters()
            dropdown = next(o for o in panel.findChildren(QObject) if o.metaObject().className().startswith('StandardDropdown_'))
            dropdown.setProperty('activeTypeFilters', ['Switch']); panel.applyFilters()
            require(rt._to_python(panel.visibleHosts()) == [], 'Legacy Switch filter behavior changed; review chapter limitation')
            dropdown.setProperty('activeTypeFilters', []); panel.applyFilters()

            m = menu_shot(FILENAMES[8], HOSTS[0])
            require(not m.property('canPing') and m.property('isWaiting'), 'Waiting menu incorrect')
            click(m, 'Connect')
            require(state(HOSTS[0]) == 'connected' and fixture.cli.sessions.has_session(HOSTS[0]), 'Connect service failed')
            inventory(FILENAMES[9])
            m = menu_shot(FILENAMES[10], HOSTS[0])
            require(m.property('canPing'), 'Connected Ping disabled')
            click(m, 'Ping'); require(fixture.cli.calls[-1][0]=='ping', 'Ping action failed')
            m=menu(HOSTS[0]); click(m, 'Save configuration')
            m=menu(HOSTS[0]); click(m, 'Sync')
            require(('sync-safe', [HOSTS[0]]) in fixture.cli.calls, 'Sync safe apply missing')
            m=menu(HOSTS[0]); click(m, 'Get running-config')
            sidebar.activateDevice(HOSTS[0]); settle()
            content = window.findChild(QObject, 'mainContentArea')
            p = content.mapToItem(window.contentItem(), QPointF(0,0))
            save(FILENAMES[16], rect=(p.x()+20,p.y()+75,770,240))

            db.updateDeviceConnectionStatus(HOSTS[3], 'disconnected'); panel.reloadDevices()
            m=menu_shot(FILENAMES[11], HOSTS[3])
            calls_before = len(fixture.cli.calls)
            click(m, 'Reconnect')
            require(state(HOSTS[3])=='waiting' and len(fixture.cli.calls)==calls_before, 'Reconnect must only reset Waiting')
            # Prepare mixed inventory; the first Connect above was driven by real menu.
            require(fixture.cli.real.connectHostAndSync(HOSTS[2])['ok'], 'SW1 preparation failed')
            db.updateDeviceConnectionStatus(HOSTS[3], 'disconnected'); panel.reloadDevices()
            panel.startMultipleSelection(HOSTS[0]); panel.selectAllVisibleHosts()
            require(set(rt._to_python(panel.property('selectedHostList')))==set(HOSTS), 'Select all count incorrect')
            inventory(FILENAMES[12])
            m=menu_shot(FILENAMES[13], HOSTS[0])
            require(rt._to_python(m.property('waitingBatchHosts'))==[HOSTS[1]], 'Waiting targets incorrect')
            require(set(rt._to_python(m.property('connectedBatchHosts')))=={HOSTS[0],HOSTS[2]}, 'Connected targets incorrect')
            click(m, 'Get configs from connected (2)')
            require(fixture.cli.calls[-1] == ('running-config', [HOSTS[0], HOSTS[2]]), 'Batch config targets differ')
            panel.startMultipleSelection(HOSTS[0]); panel.selectAllVisibleHosts()
            m = menu(HOSTS[0]); click(m, 'Connect waiting (1)')
            require(fixture.cli.calls[-1] == ('connect', [HOSTS[1]]) and state(HOSTS[1]) == 'connected', 'Batch connect targets differ')
            fixture.cli.closeDeviceSession(HOSTS[1]); panel.reloadDevices()
            dropdown.setProperty('activeStatusFilters', ['connected']); panel.applyFilters()
            require(set(rt._to_python(panel.visibleHosts())) == {HOSTS[0], HOSTS[2]}, 'Status filter differs')
            dropdown.setProperty('activeStatusFilters', []); panel.applyFilters()
            panel.startMultipleSelection(HOSTS[0]); panel.selectAllVisibleHosts()
            m = menu(HOSTS[0]); click(m, 'Disconnect connected (2)')
            require(fixture.cli.calls[-1]==('disconnect',[HOSTS[0],HOSTS[2]]), 'Disconnect targets differ')
            require(state(HOSTS[0])==state(HOSTS[2])=='waiting', 'Disconnect must reset to Waiting')
            require(not panel.property('multiSelectMode'), 'Batch completion failed to exit selection')

            m=menu(HOSTS[0]); click(m, 'Connect')
            m=menu(HOSTS[0]); click(m, 'Edit')
            new=childwin('NewDevice_')
            require(find(new, 'labelText','Host:').property('readOnly'), 'Edit Host not read-only')
            field(new,'Device Name:','Core-Router'); new.contentItem().forceActiveFocus()
            save(FILENAMES[14],new)
            click(new,'Save Changes',new)
            require(db.getDeviceByHost(HOSTS[0])['name']=='Core-Router', 'Edit did not persist')
            require(state(HOSTS[0]) == 'waiting' and not fixture.cli.sessions.has_session(HOSTS[0]), 'Edit did not close and reset session')

            # Exercise actual Import callback, skipping only the native picker.
            import_path=fixture.root/'inventory.json'
            import_path.write_text(json.dumps([{'host':TEMP,'name':'TEMP-SW','role':'sw2'}, {'host':HOSTS[0],'name':'duplicate'}]))
            panel.openBatchDeviceWindow(); batch=childwin('BatchNewDevice_')
            batch.importDevices(import_path.as_uri()); settle()
            require(len(db.getDevices())==5 and state(TEMP)=='waiting' and not batch.isVisible(), 'Import did not immediately insert and close')
            inventory(FILENAMES[17])
            # Seed related records and backups for destructive verification in temp DB only.
            with db._connect() as conn:
                conn.execute('CREATE TABLE chapter04_child (host TEXT REFERENCES t01_devices(host) ON DELETE CASCADE)')
                conn.execute('INSERT INTO chapter04_child VALUES (?)',(TEMP,))
            import sqlite3
            with sqlite3.connect(fixture.info_db) as conn:
                conn.execute('CREATE TABLE chapter04_collected (host TEXT)')
                conn.execute('INSERT INTO chapter04_collected VALUES (?)',(TEMP,))
            db._config_backup_service.save_snapshot(TEMP,'hostname TEMP-SW\n')
            m=menu(TEMP); click(m,'Delete Host…')
            delete=window.findChild(QObject,'devicePermanentDeleteDialog')
            rt._validate_dialog_structure(delete,window,'Permanently delete host?')
            save(FILENAMES[15],popup=delete)
            require(not delete.property('confirmed'), 'Delete enabled before confirmation')
            window.findChild(QObject,'deviceDeleteAcknowledgement').setProperty('checked',True)
            window.findChild(QObject,'deviceDeleteConfirmationField').setProperty('text','DELETE '+TEMP)
            require(delete.property('confirmed'), 'Delete confirmation did not enable')
            click(window,'Permanently Delete')
            require(not db.getDeviceByHost(TEMP), 'Delete failed')
            with db._connect() as conn:
                require(conn.execute('SELECT count(*) FROM chapter04_child').fetchone()[0]==0,'Related configuration retained')
            with sqlite3.connect(fixture.info_db) as conn:
                require(conn.execute('SELECT count(*) FROM chapter04_collected').fetchone()[0]==0,'Collected data retained')
            require(not (fixture.root/'backup'/TEMP).exists(),'Backup retained')
            require(len(db.getDevices())==4,'Deletion affected other hosts')
            require(set(r.path.name for r in results)==set(FILENAMES),'Incomplete shot set')
            request.output_dir.mkdir(parents=True,exist_ok=True)
            published=[]
            for result in sorted(results,key=lambda r:r.path.name):
                target=request.output_dir/result.path.name
                rt._save_png_atomic(rt.QImage(str(result.path)), target)
                published.append(rt.RenderResult(target,result.width,result.height))
            return tuple(published)
        finally:
            rt._dispose_qml_window(app,engine,window)
