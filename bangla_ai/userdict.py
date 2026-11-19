"""Words the user has picked before, so the engine learns their spelling."""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

MAX_KEYS = 50000


class UserDict:
    """Maps lowercased Banglish input -> {Bangla word: times chosen}."""

    def __init__(self, path):
        self._path = Path(path)
        self._data = {}
        self._dirty = False
        self._load()

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            log.warning("Could not read user dictionary %s: %s", self._path, e)
            return
        if not isinstance(raw, dict):
            log.warning("Ignoring malformed user dictionary %s", self._path)
            return
        for roman, words in raw.items():
            if not isinstance(roman, str) or not isinstance(words, dict):
                continue
            clean = {w: c for w, c in words.items() if isinstance(w, str) and isinstance(c, int) and c > 0}
            if clean:
                self._data[roman] = clean

    def learn(self, roman, word):
        key = roman.lower()
        if not key or not word:
            return
        if key not in self._data and len(self._data) >= MAX_KEYS:
            return
        bucket = self._data.setdefault(key, {})
        bucket[word] = bucket.get(word, 0) + 1
        self._dirty = True

    def exact(self, roman):
        """Words chosen before for exactly these letters, most used first."""
        bucket = self._data.get(roman.lower(), {})
        return [w for w, _ in sorted(bucket.items(), key=lambda item: -item[1])]

    def completions(self, roman, limit=4):
        """Words chosen before for longer input that starts with these letters."""
        prefix = roman.lower()
        if not prefix:
            return []
        found = []
        for key, bucket in self._data.items():
            if key != prefix and key.startswith(prefix):
                found.extend((count, word) for word, count in bucket.items())
        found.sort(key=lambda item: -item[0])
        words = []
        for _, word in found:
            if word not in words:
                words.append(word)
            if len(words) >= limit:
                break
        return words

    def save(self):
        if not self._dirty:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            # What the user typed is private: keep the file readable only by them.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self._path)
            self._dirty = False
        except OSError as e:
            log.warning("Could not save user dictionary %s: %s", self._path, e)
