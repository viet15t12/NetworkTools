"""Architecture contracts protecting the core split compatibility surface."""

from __future__ import annotations

import inspect
import ast
import unittest
from pathlib import Path

from core.database import DatabaseManager
from core.runtime import TerminalHelper as CompatibilityTerminalHelper
from core.tasks import AsyncTaskCoordinator
from core.terminal import TerminalHelper


APP_DIR = Path(__file__).resolve().parents[1]


class CoreRefactorContractTests(unittest.TestCase):
    """Prevent the completed low-risk boundaries from collapsing into runtime again."""

    def test_compatibility_imports_keep_public_classes(self) -> None:
        """Old imports resolve to the same owning implementations."""
        self.assertIs(CompatibilityTerminalHelper, TerminalHelper)
        self.assertTrue(inspect.isclass(DatabaseManager))
        self.assertTrue(inspect.isclass(AsyncTaskCoordinator))

    def test_terminal_has_no_database_manager_dependency(self) -> None:
        """Closing a session must not construct or import DatabaseManager."""
        source = (APP_DIR / "core" / "terminal.py").read_text(encoding="utf-8")
        self.assertNotIn("core.database", source)
        self.assertNotIn("DatabaseManager", source)

    def test_only_infrastructure_defines_session_registry(self) -> None:
        """Keep one DeviceSessionRegistry implementation across the application."""
        definitions = []
        for path in (APP_DIR / "core").rglob("*.py"):
            if "class DeviceSessionRegistry" in path.read_text(encoding="utf-8"):
                definitions.append(path)
        for path in (APP_DIR / "infrastructure").rglob("*.py"):
            if "class DeviceSessionRegistry" in path.read_text(encoding="utf-8"):
                definitions.append(path)
        self.assertEqual(definitions, [APP_DIR / "infrastructure" / "network" / "session_registry.py"])

    def test_database_slot_functions_are_documented(self) -> None:
        """Require clear docstrings on every function introduced by the package split."""
        missing = []
        for path in (APP_DIR / "core" / "database").glob("*_slots.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node) is None:
                    missing.append(f"{path.name}:{node.name}")
        self.assertFalse(missing, "Missing database slot docstrings:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
