import unittest

from features.syslog.transport.framing import FrameTooLarge, LineFramer


class LineFramerTests(unittest.TestCase):
    def test_handles_partial_and_multiple_frames(self) -> None:
        framer = LineFramer(64)
        self.assertEqual(framer.feed(b"one\ntw"), [b"one"])
        self.assertEqual(framer.feed(b"o\nthree\r\n"), [b"two", b"three"])
        self.assertEqual(framer.finish(), [])

    def test_preserves_final_unterminated_frame(self) -> None:
        framer = LineFramer(64)
        self.assertEqual(framer.feed(b"final"), [])
        self.assertEqual(framer.finish(), [b"final"])

    def test_rejects_oversized_frame(self) -> None:
        framer = LineFramer(4)
        with self.assertRaises(FrameTooLarge):
            framer.feed(b"12345")


if __name__ == "__main__":
    unittest.main()
