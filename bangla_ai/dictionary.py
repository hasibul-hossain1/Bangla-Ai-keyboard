"""Offline Bangla dictionary with loose (Avro-style) phonetic matching.

Banglish is ambiguous: "t" can mean ত or ট, "s" স, শ or ষ, "i" ই or ঈ, and most people
skip hasanta details or the word-final ো. The phonetic rules alone cannot pick the right
spelling, so every dictionary word is reduced to a *skeleton* that drops exactly those
distinctions, and the typed word is reduced the same way after transliteration:

    "bhalo"   -> ভাল    -> skeleton ভাল -> matches ভালো, ভাল
    "shikkha" -> শিক্ষা -> skeleton সিখা -> matches শিক্ষা
    "porikkha"-> পরিক্ষা -> skeleton পরিখা -> matches পরীক্ষা

Matches are ranked by how common the word is.
"""

import bisect
import logging
from pathlib import Path

from . import phonetic

log = logging.getLogger(__name__)

WORDS_FILE = Path(__file__).parent / "data" / "words.txt"

NUKTA = "়"
HASANTA = phonetic.HASANTA

# Letter groups people do not tell apart while typing Banglish -> one representative.
_FOLD = {
    # vowels: independent and dependent forms fold together; ো and inherent অ vanish
    # after a consonant, but a word-initial অ/ও stays (ওরা must not match রা).
    "আ": "া", "া": "া",
    "ই": "ি", "ঈ": "ি", "ি": "ি", "ী": "ি",
    "উ": "ু", "ঊ": "ু", "ু": "ু", "ূ": "ু",
    "এ": "ে", "ে": "ে",
    "ঐ": "অি", "ৈ": "ি",
    "ঔ": "অু", "ৌ": "ু",
    "ঋ": "রি", "ৃ": "রি",
    "অ": "অ", "ও": "অ", "ো": "",
    # consonants
    "ট": "ত", "ৎ": "ত", "ঠ": "থ", "ড": "দ", "ঢ": "ধ",
    "ণ": "ন", "ঞ": "ন",
    "শ": "স", "ষ": "স",
    "য": "জ",
    "ঙ": "ং",
    "ফ": "ফ", "ভ": "ভ",
    # signs that rarely matter for matching
    "ঁ": "", "ঃ": "", HASANTA: "", "‌": "", "‍": "",
}
# Nukta letters (NFC keeps them as base + nukta).
_NUKTA_FOLD = {"য": "য়", "ড": "র", "ঢ": "র"}
# Conjuncts that are usually typed by their sound: ক্ষ as "kh", জ্ঞ as "gy", and
# ya-fola / a silent ba-fola left out ("dhonnobad" ধন্যবাদ, "shami" স্বামী, "jor" জ্বর).
_CLUSTERS = (
    ("ক্ষ", "খ"), ("জ্ঞ", "গজ"), ("গ্য", "গজ"), ("্য", ""),
    ("শ্ব", "শ"), ("স্ব", "স"), ("দ্ব", "দ"), ("ত্ব", "ত"), ("জ্ব", "জ"),
)


def skeleton(word):
    """Reduce a Bangla word to the form used for loose matching."""
    word = phonetic.normalize(word)
    for cluster, replacement in _CLUSTERS:
        word = word.replace(cluster, replacement)
    out = []
    i = 0
    while i < len(word):
        ch = word[i]
        if i + 1 < len(word) and word[i + 1] == NUKTA and ch in _NUKTA_FOLD:
            folded = _NUKTA_FOLD[ch]
            i += 2
        else:
            folded = _FOLD.get(ch, ch)
            i += 1
        for c in folded:
            # Doubled letters are often typed once ("onek" / "onnek"): collapse them.
            if not (out and out[-1] == c and c not in "ািুে"):
                out.append(c)
    return "".join(out)


def _explicit_case(roman):
    """True when the user typed a case-sensitive capital (T, D, N, S, ...) on purpose."""
    return any(ch.isupper() and ch.lower() in phonetic.CASE_SENSITIVE for ch in roman)


class Dictionary:
    def __init__(self, entries=()):
        """entries: iterable of (word, count)."""
        self._index = {}  # skeleton -> [(count, word)], most common first
        for word, count in entries:
            word = phonetic.normalize(word)
            key = skeleton(word)
            if key:
                self._index.setdefault(key, []).append((count, word))
        for bucket in self._index.values():
            bucket.sort(key=lambda item: -item[0])
        self._keys = sorted(self._index)
        # Highest count under each key, for ranking completions without re-sorting buckets.
        self._top = {key: bucket[0][0] for key, bucket in self._index.items()}

    @classmethod
    def load(cls, path=WORDS_FILE):
        entries = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    word, _, count = line.rstrip("\n").partition("\t")
                    if word and count.isdigit():
                        entries.append((word, int(count)))
        except OSError as e:
            log.warning("Could not read dictionary %s: %s", path, e)
        dictionary = cls(entries)
        log.info("Dictionary: %d words", len(entries))
        return dictionary

    def __len__(self):
        return sum(len(bucket) for bucket in self._index.values())

    def lookup(self, roman, limit=5):
        """Dictionary words that sound like the whole Banglish input, most common first."""
        rule_words = phonetic.candidates(roman)
        if not rule_words:
            return []
        bucket = self._index.get(skeleton(rule_words[0]), [])
        words = [word for _, word in bucket[:limit]]
        if _explicit_case(roman):
            # "Tak" should give টাক even if তাক is more common.
            exact = [w for w in rule_words if w in words]
            words = exact + [w for w in words if w not in exact]
        return words

    def completions(self, roman, limit=4, min_len=2):
        """Common longer words that start like the input ("bangl" -> বাংলা, বাংলাদেশ)."""
        rule_words = phonetic.candidates(roman)
        if not rule_words:
            return []
        prefix = skeleton(rule_words[0])
        if len(prefix) < min_len:
            return []
        start = bisect.bisect_right(self._keys, prefix)
        end = bisect.bisect_left(self._keys, prefix + "￿", lo=start)
        best = sorted(self._keys[start:end], key=lambda key: -self._top[key])[:limit]
        found = []
        for key in best:
            found.extend(self._index[key][:2])
        found.sort(key=lambda item: -item[0])
        return [word for _, word in found[:limit]]

    def candidates(self, roman):
        """Local candidates: dictionary matches, then the phonetic rule variants, then completions."""
        words = []
        for word in self.lookup(roman) + phonetic.candidates(roman) + self.completions(roman):
            if word not in words:
                words.append(word)
        return words
