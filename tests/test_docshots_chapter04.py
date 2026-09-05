"""Chapter 4 integration: real QML actions/services, no network, repeatable PNGs."""
from __future__ import annotations
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from docshots.cli import APP_DIR, build_parser, main

class Chapter04DocshotTests(unittest.TestCase):
    def test_cli_destination(self):
        self.assertEqual(build_parser().parse_args(['chapter-04']).shot, 'chapter-04')
        expected = APP_DIR / 'book/figures/gui/chapter-04'
        with patch('docshots.cli.ensure_output_directory', return_value=expected) as mkdir, \
             patch('docshots.chapter04.render_chapter_04_workflow', return_value=()) as render:
            self.assertEqual(main(['chapter-04','--output-dir','/unused']), 0)
        mkdir.assert_called_once_with(expected)
        self.assertEqual(render.call_args.args[0].output_dir, expected)

    def test_production_workflow_twice_offline(self):
        code = '''
import sys
from pathlib import Path
from docshots.chapter04 import render_chapter_04_workflow
from docshots.runtime import RenderRequest
render_chapter_04_workflow(RenderRequest(1600,1000,2,'light',Path(sys.argv[1])))
'''
        with tempfile.TemporaryDirectory(prefix='chapter04-test-') as directory:
            root=Path(directory)
            for name in ('first','second'):
                result=subprocess.run([sys.executable,'-c',code,str(root/name)],cwd=APP_DIR,
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}, capture_output=True,text=True,timeout=180)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            from docshots.chapter04 import FILENAMES
            self.assertEqual({p.name for p in (root/'first').glob('*.png')},set(FILENAMES))
            for name in FILENAMES:
                first=(root/'first'/name).read_bytes();second=(root/'second'/name).read_bytes()
                self.assertEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest(),name)
            self.assertFalse(list(root.glob('.chapter04-*')))

    def test_import_sample_limitation_and_validation(self):
        from docshots.chapter04 import Fixture, HOSTS
        from docshots import runtime as rt
        rt._application()
        with tempfile.TemporaryDirectory() as directory, Fixture(rt.RenderRequest(1600,1000,1,'light',Path(directory))) as f:
            db=f.db_manager
            # Driver protocol declarations are broader than the CLI session implementation.
            self.assertTrue(db.addDevice(HOSTS[0], 'R1','NETCONF','830','','','cisco_ios','rou',''))
            self.assertFalse(f.cli.real.connectHostAndSync(HOSTS[0])['ok'])
            self.assertEqual(db.getDevices()[0]['status'],'disconnected')
            self.assertFalse(db.addDevice(HOSTS[1], 'R2','SSH','65536','','','cisco_ios','rou',''))
            self.assertTrue(db.updateDevice(HOSTS[0],'Core-Router','SSH','2222','admin','','cisco_xe','sw3',''))
            detail=db.getDeviceByHost(HOSTS[0])
            self.assertEqual((detail['ip'], detail['name'], detail['port'], detail['role']), (HOSTS[0],'Core-Router','2222','sw3'))
            import zipfile
            workbook = Path(directory)/'import.xlsx'
            with zipfile.ZipFile(workbook, 'w') as archive:
                archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>host</t></is></c><c r="B1" t="inlineStr"><is><t>name</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>192.168.56.98</t></is></c><c r="B2" t="inlineStr"><is><t>TEMP-XLSX</t></is></c></row></sheetData></worksheet>')
            imported = db.importDevicesFromFile(workbook.as_uri())
            self.assertEqual((imported['added'], imported['skipped']), (1,0))
            repeated = db.importDevicesFromFile(workbook.as_uri())
            self.assertEqual((repeated['added'], repeated['skipped']), (0,1))
            self.assertFalse(db.saveDeviceImportSample(str(Path(directory)/'sample.xlsx'))['ok'])
            self.assertTrue((APP_DIR/'templates/EXdevices.xlsx').is_file())

if __name__ == '__main__':
    unittest.main()
