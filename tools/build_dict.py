"""Build bangla_ai/data/words.txt from a "word count" frequency list.

Source used for the shipped file: the Bangla list of FrequencyWords (OpenSubtitles 2018),
https://github.com/hermitdave/FrequencyWords (content CC BY-SA 4.0):

    curl -LO https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/bn/bn_full.txt
    python3 tools/build_dict.py bn_full.txt bangla_ai/data/words.txt
"""

import argparse
import re
import sys
import unicodedata

BANGLA_WORD = re.compile(r"^[ঀ-৿‌‍]+$")
# A word has to start with an independent vowel or a consonant.
FIRST_LETTER = re.compile(r"^[অ-ঔক-হড়-য়ৎ]")
DEPENDENT = "ািীুূৃেৈোৌ"
HASANTA = "্"

HEADER = """\
# Bangla word frequency list for the Bangla AI IME dictionary: word<TAB>count.
# Derived from FrequencyWords (OpenSubtitles 2018) by Hermit Dave,
# https://github.com/hermitdave/FrequencyWords, licensed CC BY-SA 4.0.
# Filtered and normalized with tools/build_dict.py.
"""


def clean(word):
    word = unicodedata.normalize("NFC", word.strip())
    if not BANGLA_WORD.match(word) or not FIRST_LETTER.match(word):
        return None
    if word.endswith(HASANTA) or "অা" in word:
        return None
    for a, b in zip(word, word[1:]):
        # Two vowel signs or a sign after a hasanta are typos.
        if a in DEPENDENT + HASANTA and b in DEPENDENT + HASANTA:
            return None
    return word


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--min-count", type=int, default=3)
    args = parser.parse_args()

    counts = {}
    with open(args.source, encoding="utf-8") as f:
        for line in f:
            parts = line.rsplit(None, 1)
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            word = clean(parts[0])
            if word:
                counts[word] = counts.get(word, 0) + int(parts[1])

    words = sorted(((w, c) for w, c in counts.items() if c >= args.min_count), key=lambda item: (-item[1], item[0]))
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(HEADER)
        for word, count in words:
            f.write(f"{word}\t{count}\n")
    print(f"{len(words)} words -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
