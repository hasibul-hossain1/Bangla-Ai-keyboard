import json
import os
import tempfile
import unittest
from pathlib import Path

from bangla_ai.userdict import UserDict


class UserDictTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "user_dict.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_exact_orders_by_use(self):
        d = UserDict(self.path)
        d.learn("korbo", "কর্ব")
        d.learn("korbo", "করবো")
        d.learn("korbo", "করবো")
        self.assertEqual(d.exact("korbo"), ["করবো", "কর্ব"])

    def test_lookup_ignores_case(self):
        d = UserDict(self.path)
        d.learn("Thik", "ঠিক")
        self.assertEqual(d.exact("thik"), ["ঠিক"])

    def test_completions_skip_exact_key(self):
        d = UserDict(self.path)
        d.learn("bha", "ভা")
        d.learn("bhalo", "ভালো")
        d.learn("bhalobasha", "ভালোবাসা")
        d.learn("bhalobasha", "ভালোবাসা")
        self.assertEqual(d.completions("bha"), ["ভালোবাসা", "ভালো"])
        self.assertEqual(d.completions(""), [])

    def test_save_and_reload(self):
        d = UserDict(self.path)
        d.learn("ami", "আমি")
        d.save()
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        self.assertEqual(UserDict(self.path).exact("ami"), ["আমি"])

    def test_malformed_file_is_ignored(self):
        self.path.write_text(json.dumps({"ami": {"আমি": "x"}, "x": 3}), encoding="utf-8")
        self.assertEqual(UserDict(self.path).exact("ami"), [])
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(UserDict(self.path).exact("ami"), [])


if __name__ == "__main__":
    unittest.main()
