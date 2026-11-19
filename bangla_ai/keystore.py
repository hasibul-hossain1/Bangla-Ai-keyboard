"""Anthropic API key storage: GNOME Keyring first, a private file as fallback."""

import logging
import os

import gi

from .config import CONFIG_DIR

try:
    gi.require_version("Secret", "1")
    from gi.repository import Secret
except (ValueError, ImportError):
    Secret = None

from gi.repository import GLib

log = logging.getLogger(__name__)

KEY_FILE = CONFIG_DIR / "api_key"
_ATTRIBUTES = {"service": "anthropic-api"}
_SCHEMA = (
    Secret.Schema.new(
        "org.kbtools.BanglaAIIME",
        Secret.SchemaFlags.NONE,
        {"service": Secret.SchemaAttributeType.STRING},
    )
    if Secret
    else None
)


def load_api_key():
    if Secret:
        try:
            key = Secret.password_lookup_sync(_SCHEMA, _ATTRIBUTES, None)
            if key:
                return key.strip()
        except GLib.Error as e:
            log.warning("Keyring lookup failed: %s", e.message)
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None
    except OSError as e:
        log.warning("Could not read %s: %s", KEY_FILE, e)
        return None


def store_api_key(key):
    """Save the key and return a description of where it went."""
    if Secret:
        try:
            stored = Secret.password_store_sync(
                _SCHEMA, _ATTRIBUTES, Secret.COLLECTION_DEFAULT,
                "Bangla AI IME - Anthropic API key", key, None,
            )
            if stored:
                _remove_key_file()
                return "GNOME Keyring"
        except GLib.Error as e:
            log.warning("Keyring store failed, using a file instead: %s", e.message)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key + "\n")
    os.chmod(KEY_FILE, 0o600)
    return str(KEY_FILE)


def clear_api_key():
    if Secret:
        try:
            Secret.password_clear_sync(_SCHEMA, _ATTRIBUTES, None)
        except GLib.Error as e:
            log.warning("Keyring clear failed: %s", e.message)
    _remove_key_file()


def _remove_key_file():
    try:
        KEY_FILE.unlink()
    except FileNotFoundError:
        pass
