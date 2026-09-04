from __future__ import annotations

import unittest

from features.syslog.source_resolver import DeviceHostResolver


class _Repository:
    def __init__(self, mapped_host: str | None) -> None:
        self.mapped_host = mapped_host
        self.calls = 0

    def resolve_device_host(self, source_ip: str) -> str | None:
        self.calls += 1
        return self.mapped_host


class DeviceHostResolverTests(unittest.TestCase):
    def test_caches_mapping_and_clears_it_when_workspace_changes(self) -> None:
        first = _Repository("router-1")
        resolver = DeviceHostResolver(first, ttl_seconds=60)

        self.assertEqual(resolver.resolve("192.0.2.1"), "router-1")
        self.assertEqual(resolver.resolve("192.0.2.1"), "router-1")
        self.assertEqual(first.calls, 1)

        second = _Repository(None)
        resolver.set_repository(second)
        self.assertEqual(resolver.resolve("192.0.2.1"), "192.0.2.1")
        self.assertEqual(second.calls, 1)


if __name__ == "__main__":
    unittest.main()
