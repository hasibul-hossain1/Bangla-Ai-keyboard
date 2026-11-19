import unittest

from bangla_ai import phonetic
from bangla_ai.phonetic import normalize


class TransliterateTest(unittest.TestCase):
    def assertConverts(self, roman, expected, **kwargs):
        self.assertEqual(phonetic.transliterate(roman, **kwargs), normalize(expected), roman)

    def test_common_words(self):
        cases = {
            "ami": "আমি",
            "tumi": "তুমি",
            "bangla": "বাংলা",
            "kemon": "কেমন",
            "achi": "আছি",
            "ekhon": "এখন",
            "bangladesh": "বাংলাদেশ",
        }
        for roman, expected in cases.items():
            self.assertConverts(roman, expected)

    def test_case_sensitive_letters(self):
        self.assertConverts("Thik", "ঠিক")
        self.assertConverts("Ami", "আমি")
        self.assertConverts("krriShi", "কৃষি")

    def test_conjuncts(self):
        self.assertConverts("onno", "অন্ন")
        self.assertConverts("porikkha", "পরিক্ষা")
        self.assertConverts("korbo", "কর্ব")
        self.assertConverts("korbo", "করব", conjuncts=False)
        self.assertConverts("k`k", "কক")

    def test_folas(self):
        self.assertConverts("byakti", "ব্যাক্তি")
        self.assertConverts("swamI", "স্বামী")

    def test_nukta_letters(self):
        self.assertConverts("kothay", "কথায়")
        self.assertConverts("gaye", "গায়ে")
        self.assertConverts("baRi", "বাড়ি")

    def test_colon(self):
        self.assertConverts("du:kho", "দুঃখ")
        self.assertConverts("ha:", "হা:")

    def test_final_o(self):
        self.assertConverts("bhalo", "ভাল")
        self.assertConverts("bhalo", "ভালো", final_o=True)


class CandidatesTest(unittest.TestCase):
    def test_standard_result_first(self):
        words = phonetic.candidates("bhalo")
        self.assertEqual(words[0], normalize("ভাল"))
        self.assertIn(normalize("ভালো"), words)

    def test_variants_without_conjuncts(self):
        self.assertIn(normalize("করবো"), phonetic.candidates("korbo"))

    def test_no_duplicates(self):
        self.assertEqual(phonetic.candidates("ami"), [normalize("আমি")])

    def test_empty_input(self):
        self.assertEqual(phonetic.candidates(""), [])
        self.assertEqual(phonetic.candidates("`"), [])


if __name__ == "__main__":
    unittest.main()
