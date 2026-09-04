import unittest

from features.devices.save_config_service import SaveConfigService


class _Connection:
    def __init__(self, output="[OK]"):
        self.output = output
        self.calls = 0

    def save_config(self):
        self.calls += 1
        return self.output


class _FallbackConnection:
    def __init__(self, fallback_output="Copy complete."):
        self.calls = []
        self.fallback_output = fallback_output

    def save_config(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs:
            return "% Invalid input detected at '^' marker."
        return self.fallback_output


class _Connector:
    def __init__(self, connection):
        self.connection = connection


class _Registry:
    def __init__(self, connector=None, failure=None):
        self.connector = connector
        self.failure = failure
        self.ensure_open = None

    def execute(self, host, operation, *, ensure_open=True):
        self.ensure_open = ensure_open
        if self.failure:
            return {"ok": False, "severity": "error", "message": self.failure}
        try:
            return {"ok": True, "value": operation(self.connector)}
        except Exception as exc:
            return {"ok": False, "severity": "error", "message": str(exc)}


class SaveConfigServiceTests(unittest.TestCase):
    def test_explicit_copy_helper_never_uses_write_memory(self):
        connection = _FallbackConnection()

        output = SaveConfigService.copy_running_to_startup(_Connector(connection))

        self.assertEqual(output, "Copy complete.")
        self.assertEqual(
            connection.calls,
            [{"cmd": "copy running-config startup-config", "confirm": True}],
        )

    def test_save_uses_driver_and_never_opens_a_session_implicitly(self):
        connection = _Connection("Building configuration...\n[OK]")
        registry = _Registry(_Connector(connection))

        result = SaveConfigService(registry).save("192.0.2.10")

        self.assertTrue(result["ok"])
        self.assertEqual(connection.calls, 1)
        self.assertFalse(registry.ensure_open)
        self.assertIn("startup configuration", result["message"])

    def test_missing_driver_capability_fails_closed(self):
        registry = _Registry(_Connector(object()))

        result = SaveConfigService(registry).save("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertIn("does not support", result["message"])

    def test_invalid_command_output_is_not_reported_as_success(self):
        registry = _Registry(_Connector(_Connection("% Invalid input detected")))

        result = SaveConfigService(registry).save("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertIn("rejected", result["message"])

    def test_invalid_write_memory_falls_back_to_copy_running_config(self):
        connection = _FallbackConnection()
        registry = _Registry(_Connector(connection))

        result = SaveConfigService(registry).save("192.0.2.10")

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            connection.calls,
            [
                {},
                {
                    "cmd": "copy running-config startup-config",
                    "confirm": True,
                },
            ],
        )

    def test_rejected_fallback_is_not_reported_as_success(self):
        connection = _FallbackConnection("% Invalid input detected")
        registry = _Registry(_Connector(connection))

        result = SaveConfigService(registry).save("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertIn("both supported", result["message"])


if __name__ == "__main__":
    unittest.main()
