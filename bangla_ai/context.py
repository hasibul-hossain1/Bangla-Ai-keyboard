"""Working out the text before the cursor, which Claude gets as context.

Apps that support it share their text with the input method ("surrounding text"). Using
it, the context follows the cursor: after a mouse click it is the text at the new place,
and it includes text typed earlier or pasted. The app refreshes the shared copy just
before each key press, but it may not show what that key did yet; the engine then uses
what it expects the text to be. Apps that share nothing fall back to what the engine
typed into the field itself.
"""


def before_cursor(shared, base, expected, own):
    """The text before the cursor.

    shared:   the text before the cursor as the app reports it now, or None if it shares nothing.
    base:     what the app reported when the last key was pressed, or None if unknown.
    expected: base changed by what that key typed or deleted, or None if unknown.
    own:      the engine's own record of what it typed into this field.
    """
    if shared is None:
        return own
    if base is not None and expected is not None and shared == base:
        shared = expected  # the app has not caught up with the last key yet
    # Some apps say they share their text but always send nothing.
    return shared if shared.strip() else own


def at_line_end(text, cursor):
    """True when only spaces follow the cursor on its line, so a completion fits there."""
    end = text.find("\n", cursor)
    rest = text[cursor:] if end == -1 else text[cursor:end]
    return not rest.strip()
