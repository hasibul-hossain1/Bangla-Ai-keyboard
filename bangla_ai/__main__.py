"""Command line entry point: `python -m bangla_ai`."""

import argparse
import getpass
import logging
import logging.handlers
import sys

from .config import CACHE_DIR, CONFIG_FILE, LOG_FILE


def _setup_logging(to_file):
    if to_file:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=1, encoding="utf-8"
        )
    else:
        handler = logging.StreamHandler()
    # Never log typed text or the API key, only events and errors.
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _set_key():
    from . import keystore

    key = getpass.getpass("Anthropic API key (type korle dekhabe na): ").strip()
    if not key:
        print("Kono key deya hoyni, kichu change hoyni.")
        return 1
    where = keystore.store_api_key(key)
    print(f"Key save hoyeche: {where}")
    print("Engine 60 second er moddhe notun key nibe (ba: ibus restart).")
    return 0


def _clear_key():
    from . import keystore

    keystore.clear_api_key()
    print("API key muche fela hoyeche.")
    return 0


def _show(words):
    from .dictionary import Dictionary

    dictionary = Dictionary.load()
    for word in words:
        print(f"{word}: {'  '.join(dictionary.candidates(word))}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="bangla-ai-ime", description="Bangla AI input method for IBus")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ibus", action="store_true", help="run as the engine (ibus-daemon uses this)")
    group.add_argument("--debug", action="store_true", help="run in the foreground and switch to the engine")
    group.add_argument("--set-key", action="store_true", help="save the Anthropic API key")
    group.add_argument("--clear-key", action="store_true", help="delete the saved API key")
    group.add_argument("--show", nargs="+", metavar="WORD", help="print local candidates for Banglish words")
    args = parser.parse_args()

    if args.set_key:
        _setup_logging(to_file=False)
        return _set_key()
    if args.clear_key:
        _setup_logging(to_file=False)
        return _clear_key()
    if args.show:
        return _show(args.show)
    if args.ibus or args.debug:
        _setup_logging(to_file=args.ibus)
        from . import app

        app.run(exec_by_ibus=args.ibus)
        return 0
    parser.print_help()
    print(f"\nSettings: {CONFIG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
