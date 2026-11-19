"""Settings and XDG paths."""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

APP_NAME = "bangla-ai-ime"
VERSION = "0.1.0"


def _xdg_dir(env_var, fallback):
    value = os.environ.get(env_var)
    return Path(value) if value else Path.home() / fallback


CONFIG_DIR = _xdg_dir("XDG_CONFIG_HOME", ".config") / APP_NAME
DATA_DIR = _xdg_dir("XDG_DATA_HOME", ".local/share") / APP_NAME
CACHE_DIR = _xdg_dir("XDG_CACHE_HOME", ".cache") / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
USER_DICT_FILE = DATA_DIR / "user_dict.json"
LOG_FILE = CACHE_DIR / "engine.log"

DEFAULTS = {
    # Claude model and how much it thinks. Lower effort answers faster.
    "model": "claude-opus-5-5",
    "effort": "low",
    # Master switch for sending typed text to the Claude API.
    "claude_enabled": True,
    # Show Claude's continuation inline (Tab accepts, Esc dismisses).
    "inline_completion": True,
    # Highlight Claude's top word when it arrives, so Space commits it.
    "auto_select_claude": False,
    # Pause (ms) after the last keystroke before asking Claude.
    "debounce_ms": 400,
    # How many recently typed characters are sent as context.
    "context_chars": 120,
    # Next-word prediction only starts after this many typed words.
    "min_prediction_words": 1,
    "max_claude_words": 4,
    "request_timeout_seconds": 8.0,
    # Type 0-9 as Bangla digits.
    "bangla_digits": False,
    # Type "." as "।" (not after a digit).
    "dari_for_period": True,
}


def _valid(value, default):
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, type(default))


def load_config():
    config = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user = json.load(f)
    except FileNotFoundError:
        save_config(config)
        return config
    except (OSError, ValueError) as e:
        log.warning("Could not read %s, using defaults: %s", CONFIG_FILE, e)
        return config
    if not isinstance(user, dict):
        log.warning("Ignoring malformed %s", CONFIG_FILE)
        return config
    for key, default in DEFAULTS.items():
        if key not in user:
            continue
        if _valid(user[key], default):
            config[key] = float(user[key]) if isinstance(default, float) else user[key]
        else:
            log.warning("Ignoring invalid value for %r in %s", key, CONFIG_FILE)
    return config


def save_config(config):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, CONFIG_FILE)
    except OSError as e:
        log.warning("Could not save %s: %s", CONFIG_FILE, e)
