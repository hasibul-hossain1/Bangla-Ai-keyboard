import unittest

from bangla_ai.context import at_line_end, before_cursor


class BeforeCursorTest(unittest.TestCase):
    def test_app_shares_nothing(self):
        self.assertEqual(before_cursor(None, None, None, "আমি ভাত "), "আমি ভাত ")

    def test_app_text_wins_when_it_is_up_to_date(self):
        # After a mouse click our own record is empty, but the app's text is there.
        self.assertEqual(before_cursor("আজ আমি ", None, None, ""), "আজ আমি ")
        # The app already shows what the last key typed.
        self.assertEqual(before_cursor("আজ আমি ভাত ", "আজ আমি ", "আজ আমি ভাত ", "ভাত "), "আজ আমি ভাত ")

    def test_app_not_caught_up_yet(self):
        self.assertEqual(before_cursor("আজ আমি ", "আজ আমি ", "আজ আমি ভাত ", "ভাত "), "আজ আমি ভাত ")
        # A Backspace the app has not reported yet.
        self.assertEqual(before_cursor("আমি ভাত", "আমি ভাত", "আমি ভা", ""), "আমি ভা")

    def test_cursor_moved_without_a_reset(self):
        # The app's text no longer matches the last key: it is the new place, use it.
        self.assertEqual(before_cursor("অন্য লাইন ", "আজ আমি ", "আজ আমি ভাত ", "আজ আমি ভাত "), "অন্য লাইন ")

    def test_app_sends_empty_text(self):
        self.assertEqual(before_cursor("", None, None, "আমি "), "আমি ")
        self.assertEqual(before_cursor("  ", "  ", "  ", "আমি "), "আমি ")


class AtLineEndTest(unittest.TestCase):
    def test_line_end(self):
        self.assertTrue(at_line_end("আমি ভাত", 7))
        self.assertTrue(at_line_end("আমি ভাত  \nপরের লাইন", 7))
        self.assertTrue(at_line_end("", 0))

    def test_middle_of_text(self):
        self.assertFalse(at_line_end("আমি ভাত খাই", 4))
        self.assertFalse(at_line_end("আমি ভাত খাই\n", 4))


if __name__ == "__main__":
    unittest.main()
