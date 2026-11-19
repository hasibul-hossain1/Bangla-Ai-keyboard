"""Avro-style phonetic transliteration: Banglish (Latin letters) -> Bangla.

The rules follow the familiar Avro Phonetic conventions:

* a vowel right after a consonant becomes a vowel sign (kar), otherwise the
  independent vowel is used ("ami" -> আমি);
* "o" after a consonant is the inherent vowel and produces nothing
  ("kemon" -> কেমন), on its own it is অ;
* two consonants with no vowel between them form a conjunct ("onno" -> অন্ন),
  and "`" breaks a conjunct without adding anything;
* only the letters o i u d g j n r s t y z are case sensitive
  (T = ট, t = ত, S = শ, Sh = ষ, ...); every other letter is lowercased.

`candidates()` also returns the most useful variants (word-final "o" as ো,
no automatic conjuncts) so the user can pick what they meant.
"""

import unicodedata

HASANTA = "্"  # ্

# Bangla letters with a nukta, written in their canonical (NFC) form.
YA_NUKTA = "য়"  # য়
RRA = "ড়"  # ড়
RHA = "ঢ়"  # ঢ়

CASE_SENSITIVE = set("oiudgjnrstyz")

VOWELS = {
    "rri": ("ঋ", "ৃ"),
    "OI": ("ঐ", "ৈ"),
    "OU": ("ঔ", "ৌ"),
    "oo": ("উ", "ু"),
    "ee": ("ঈ", "ী"),
    "a": ("আ", "া"),
    "i": ("ই", "ি"),
    "I": ("ঈ", "ী"),
    "u": ("উ", "ু"),
    "U": ("ঊ", "ূ"),
    "e": ("এ", "ে"),
    "O": ("ও", "ো"),
    "o": ("অ", ""),
}

# Consonants that join the next consonant with a hasanta.
CONSONANTS = {
    "kkh": "ক্ষ",
    "kSh": "ক্ষ",
    "ksh": "ক্ষ",
    "nggh": "ঙ্ঘ",
    "ngkh": "ঙ্খ",
    "ngg": "ঙ্গ",
    "ngk": "ঙ্ক",
    "chh": "ছ",
    "rZ": "র‍্য",
    "kh": "খ",
    "gh": "ঘ",
    "ch": "ছ",
    "jh": "ঝ",
    "Th": "ঠ",
    "Dh": "ঢ",
    "th": "থ",
    "dh": "ধ",
    "ph": "ফ",
    "bh": "ভ",
    "sh": "শ",
    "Sh": "ষ",
    "Ng": "ঙ",
    "NG": "ঞ",
    "k": "ক",
    "g": "গ",
    "G": "গ",
    "c": "চ",
    "j": "জ",
    "J": "জ",
    "T": "ট",
    "D": "ড",
    "N": "ণ",
    "t": "ত",
    "d": "দ",
    "n": "ন",
    "p": "প",
    "f": "ফ",
    "b": "ব",
    "v": "ভ",
    "m": "ম",
    "z": "য",
    "r": "র",
    "l": "ল",
    "S": "শ",
    "s": "স",
    "h": "হ",
    "q": "ক",
    "x": "ক্স",
}

# Consonants that take a vowel sign but never form a conjunct.
NON_JOINING = {
    "Rh": RHA,
    "R": RRA,
    "Y": YA_NUKTA,
}

# Signs that take no vowel sign and never join.
SIGNS = {
    "t``": "ৎ",
    "ng": "ং",
    "^": "ঁ",
}

# Letters that become a "fola" after a consonant:
# roman -> (kind when standalone, standalone text, fola text)
FOLAS = {
    "y": ("N", YA_NUKTA, HASANTA + "য"),
    "w": ("V", "ও", HASANTA + "ব"),
    "Z": ("C", "য", HASANTA + "য"),
}


def _build_patterns():
    patterns = {}
    for roman, forms in VOWELS.items():
        patterns[roman] = ("V", forms)
    for roman, text in CONSONANTS.items():
        patterns[roman] = ("C", text)
    for roman, text in NON_JOINING.items():
        patterns[roman] = ("N", text)
    for roman, text in SIGNS.items():
        patterns[roman] = ("S", text)
    for roman, forms in FOLAS.items():
        patterns[roman] = ("F", forms)
    patterns["`"] = ("SEP", "")
    patterns[":"] = ("COLON", "ঃ")
    return patterns


PATTERNS = _build_patterns()
MAX_PATTERN_LEN = max(len(roman) for roman in PATTERNS)


def normalize_case(text):
    """Lowercase every letter whose case carries no meaning in Avro."""
    return "".join(ch if ch.lower() in CASE_SENSITIVE else ch.lower() for ch in text)


def tokenize(text):
    """Split Banglish text into (kind, value, roman) tokens by longest match."""
    text = normalize_case(text)
    tokens = []
    i = 0
    while i < len(text):
        for size in range(min(MAX_PATTERN_LEN, len(text) - i), 0, -1):
            chunk = text[i:i + size]
            if chunk in PATTERNS:
                kind, value = PATTERNS[chunk]
                tokens.append((kind, value, chunk))
                i += size
                break
        else:
            ch = text[i]
            if ch.lower() in PATTERNS:
                kind, value = PATTERNS[ch.lower()]
                tokens.append((kind, value, ch.lower()))
            else:
                tokens.append(("RAW", ch, ch))
            i += 1
    return tokens


def transliterate(text, conjuncts=True, final_o=False):
    """Convert one Banglish word to Bangla.

    conjuncts: join consecutive consonants with a hasanta.
    final_o:   write a word-final "o" after a consonant as ো instead of the
               inherent vowel ("bhalo" -> ভালো instead of ভাল).
    """
    tokens = tokenize(text)
    out = []
    prev_cons = False  # previous token takes a vowel sign
    prev_joinable = False  # previous token joins a following consonant
    last = len(tokens) - 1
    for idx, (kind, value, roman) in enumerate(tokens):
        if kind == "V":
            independent, kar = value
            if prev_cons:
                if roman == "o" and final_o and idx == last:
                    out.append("ো")
                else:
                    out.append(kar)
            else:
                out.append(independent)
            prev_cons = prev_joinable = False
        elif kind == "C":
            if prev_joinable and conjuncts:
                out.append(HASANTA)
            out.append(value)
            prev_cons = prev_joinable = True
        elif kind == "N":
            out.append(value)
            prev_cons, prev_joinable = True, False
        elif kind == "F":
            standalone_kind, standalone, fola = value
            if prev_cons:
                out.append(fola)
                prev_joinable = False
            else:
                out.append(standalone)
                prev_cons = standalone_kind in ("C", "N")
                prev_joinable = standalone_kind == "C"
        elif kind == "S":
            out.append(value)
            prev_cons = prev_joinable = False
        elif kind == "COLON":
            # A trailing colon is punctuation; inside a word it is visarga.
            out.append(value if idx != last else ":")
            prev_cons = prev_joinable = False
        elif kind == "SEP":
            prev_joinable = False
        else:
            out.append(value)
            prev_cons = prev_joinable = False
    return normalize("".join(out))


def candidates(text):
    """Local candidates for one Banglish word: the standard Avro result first."""
    words = []
    for conjuncts, final_o in ((True, False), (True, True), (False, False), (False, True)):
        word = transliterate(text, conjuncts=conjuncts, final_o=final_o)
        if word and word not in words:
            words.append(word)
    return words


def normalize(text):
    """Canonical form used to compare words from different sources."""
    return unicodedata.normalize("NFC", text)


def has_bangla(text):
    return any("ঀ" <= ch <= "৿" for ch in text)
