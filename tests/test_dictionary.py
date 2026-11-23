import unittest

from bangla_ai import phonetic
from bangla_ai.dictionary import Dictionary, skeleton
from bangla_ai.phonetic import normalize

SAMPLE = [
    ("আমি", 1000), ("ভালো", 480), ("ভাল", 450), ("কি", 900), ("কী", 300),
    ("পরীক্ষা", 40), ("শিক্ষা", 20), ("শিখা", 5), ("ধন্যবাদ", 60), ("স্বামী", 30),
    ("তাক", 50), ("টাক", 10), ("টাকা", 200), ("ওরা", 300), ("রা", 5),
    ("বাংলা", 100), ("বাংলাদেশ", 80), ("জ্ঞান", 25), ("গান", 90), ("করবো", 70), ("করব", 60),
]


def n(words):
    return [normalize(w) for w in words]


class SkeletonTest(unittest.TestCase):
    def test_folds_confusable_letters(self):
        self.assertEqual(skeleton("পরীক্ষা"), skeleton("পরিখা"))
        self.assertEqual(skeleton("ভালো"), skeleton("ভাল"))
        self.assertEqual(skeleton("ধন্যবাদ"), skeleton("ধন্নবাদ"))
        self.assertEqual(skeleton("স্বামী"), skeleton("শামি"))
        self.assertEqual(skeleton("বাড়ি"), skeleton("বারি"))

    def test_keeps_initial_o(self):
        self.assertNotEqual(skeleton("ওরা"), skeleton("রা"))


class DictionaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Dictionary(SAMPLE)

    def test_common_spelling_first(self):
        self.assertEqual(self.d.candidates("bhalo")[:2], n(["ভালো", "ভাল"]))
        self.assertEqual(self.d.candidates("porikkha")[0], normalize("পরীক্ষা"))
        self.assertEqual(self.d.candidates("shikkha")[0], normalize("শিক্ষা"))
        self.assertEqual(self.d.candidates("dhonnobad")[0], normalize("ধন্যবাদ"))
        self.assertEqual(self.d.candidates("shami")[0], normalize("স্বামী"))
        self.assertEqual(self.d.candidates("korbo")[0], normalize("করবো"))
        self.assertEqual(self.d.candidates("gyan")[0], normalize("জ্ঞান"))

    def test_explicit_capital_wins(self):
        self.assertEqual(self.d.candidates("tak")[0], normalize("তাক"))
        self.assertEqual(self.d.candidates("Tak")[0], normalize("টাক"))

    def test_initial_o_is_not_dropped(self):
        self.assertEqual(self.d.candidates("ra")[0], normalize("রা"))
        self.assertEqual(self.d.candidates("ora")[0], normalize("ওরা"))

    def test_completions(self):
        self.assertEqual(self.d.completions("bangl"), n(["বাংলা", "বাংলাদেশ"]))
        self.assertEqual(self.d.completions("k"), [])  # too short to be useful

    def test_unknown_word_falls_back_to_rules(self):
        self.assertEqual(self.d.candidates("pothik"), phonetic.candidates("pothik"))
        self.assertEqual(Dictionary().candidates("ami"), n(["আমি"]))

    def test_rule_variants_kept(self):
        self.assertIn(normalize("কর্ব"), self.d.candidates("korbo"))

    def test_empty_input(self):
        self.assertEqual(self.d.candidates(""), [])


class ShippedDictionaryTest(unittest.TestCase):
    def test_loads(self):
        d = Dictionary.load()
        self.assertGreater(len(d), 20000)
        self.assertEqual(d.candidates("ami")[0], normalize("আমি"))
        self.assertEqual(d.candidates("bhalo")[0], normalize("ভালো"))


if __name__ == "__main__":
    unittest.main()
