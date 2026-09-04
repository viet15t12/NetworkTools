from __future__ import annotations

from pathlib import Path
import unittest


class ParameterHelpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.component = (
            root / "UI/components/standard/ParameterHelpButton.qml"
        ).read_text(encoding="utf-8")

    def test_help_dialog_adapts_without_horizontal_clipping(self) -> None:
        self.assertIn("readonly property bool compactLayout: width < 600", self.component)
        self.assertIn("contentWidth: availableWidth", self.component)
        self.assertIn("ScrollBar.horizontal.policy: ScrollBar.AlwaysOff", self.component)
        self.assertIn("width: helpScroll.availableWidth", self.component)
        self.assertGreaterEqual(self.component.count("Layout.minimumWidth: 0"), 6)
        self.assertGreaterEqual(self.component.count("wrapMode: Text.Wrap"), 4)

    def test_help_dialog_has_scannable_visual_hierarchy(self) -> None:
        self.assertIn('text: "Quick parameter guide"', self.component)
        self.assertIn('objectName: "parameterHelpEntryCard"', self.component)
        self.assertIn('objectName: "parameterHelpEntryLabel"', self.component)
        self.assertIn('objectName: "parameterHelpEntryDetail"', self.component)
        self.assertIn("text: helpEntry.index + 1", self.component)


if __name__ == "__main__":
    unittest.main()
