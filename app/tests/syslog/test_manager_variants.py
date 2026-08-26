import unittest

from PyQt6.QtQml import QJSEngine
from PyQt6.QtWidgets import QApplication

from features.syslog.qt.manager import _variant_dict, _variant_list


class SyslogManagerVariantTests(unittest.TestCase):
    def test_qml_filter_object_converts_to_python_dict(self) -> None:
        _app = QApplication.instance() or QApplication([])
        engine = QJSEngine()
        filters = engine.evaluate(
            "({host: '192.0.2.1', search: 'CONFIG', severities: [4, 5]})"
        )

        result = _variant_dict(filters)

        self.assertEqual(
            result,
            {
                "host": "192.0.2.1",
                "search": "CONFIG",
                "severities": [4, 5],
            },
        )

    def test_qml_log_rows_convert_to_python_list(self) -> None:
        _app = QApplication.instance() or QApplication([])
        engine = QJSEngine()
        rows = engine.evaluate(
            "([{device_host: '192.0.2.1', message: 'up'}, "
            "{device_host: '192.0.2.2', message: 'down'}])"
        )

        result = [_variant_dict(row) for row in _variant_list(rows)]

        self.assertEqual(
            result,
            [
                {"device_host": "192.0.2.1", "message": "up"},
                {"device_host": "192.0.2.2", "message": "down"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
