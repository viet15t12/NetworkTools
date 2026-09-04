from __future__ import annotations

import unittest

from features.switching.worker import apply_commands


class _Connection:
    def __init__(self, output: str) -> None:
        self.output = output

    def send_config_set(self, _commands, **_kwargs):
        return self.output


class _Connector:
    def __init__(self, output: str) -> None:
        self.connection = _Connection(output)


class SwitchingWorkerTests(unittest.TestCase):
    def test_fixed_dot1q_switch_can_reject_only_the_capability_command(self) -> None:
        output = """SW(config-if)#switchport trunk encapsulation dot1q
                                      ^
% Invalid input detected at '^' marker.
SW(config-if)#switchport mode trunk
SW(config-if)#"""

        self.assertEqual(apply_commands(_Connector(output), ["unused"]), output)

    def test_trunk_mode_rejection_is_fatal(self) -> None:
        output = """SW(config-if)#switchport mode trunk
Command rejected: An interface whose trunk encapsulation is Auto cannot be configured to trunk mode."""

        with self.assertRaisesRegex(RuntimeError, "Command rejected"):
            apply_commands(_Connector(output), ["unused"])

    def test_other_invalid_commands_remain_fatal(self) -> None:
        output = """SW(config-if)#speed auto
                         ^
% Invalid input detected at '^' marker."""

        with self.assertRaisesRegex(RuntimeError, "speed auto"):
            apply_commands(_Connector(output), ["unused"])

    def test_real_error_after_tolerated_dot1q_error_remains_fatal(self) -> None:
        output = """SW(config-if)#switchport trunk encapsulation dot1q
                                      ^
% Invalid input detected at '^' marker.
SW(config-if)#switchport mode trunk
                         ^
% Invalid input detected at '^' marker."""

        with self.assertRaisesRegex(RuntimeError, "switchport mode trunk"):
            apply_commands(_Connector(output), ["unused"])


if __name__ == "__main__":
    unittest.main()
