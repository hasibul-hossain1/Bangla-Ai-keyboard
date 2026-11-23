"""The IBus engine: Banglish key presses -> Bangla, with a candidate popup and inline completions."""

import logging

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus

from . import phonetic
from .config import save_config
from .context import at_line_end, before_cursor

log = logging.getLogger(__name__)

PAGE_SIZE = 9
CLAUDE_MARK = " ✦"
GHOST_COLOR = 0x8A8A8A
CONTEXT_KEEP = 400
BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

MODIFIER_KEYS = {
    IBus.KEY_Shift_L, IBus.KEY_Shift_R, IBus.KEY_Control_L, IBus.KEY_Control_R,
    IBus.KEY_Alt_L, IBus.KEY_Alt_R, IBus.KEY_Super_L, IBus.KEY_Super_R,
    IBus.KEY_Meta_L, IBus.KEY_Meta_R, IBus.KEY_Caps_Lock, IBus.KEY_ISO_Level3_Shift,
}
SHORTCUT_MASK = (
    IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK
    | IBus.ModifierType.SUPER_MASK | IBus.ModifierType.MOD4_MASK
)
ENTER_KEYS = {IBus.KEY_Return, IBus.KEY_KP_Enter}

STATUS_HINTS = {
    "no-key": "✦ API key set kora nei",
    "auth": "✦ API key thik nei",
    "rate-limit": "✦ rate limit, ektu por",
    "offline": "✦ offline",
    "error": "✦ Claude error",
}


def _unique(words):
    result = []
    for word in words:
        if word and word not in result:
            result.append(word)
    return result


class BanglaAIEngine(IBus.Engine):
    __gtype_name__ = "BanglaAIEngine"

    # Shared by every engine instance; set by app.run() before the factory starts.
    services = None

    def __init__(self):
        super().__init__()
        self._config = self.services.config
        self._userdict = self.services.userdict
        self._dictionary = self.services.dictionary
        self._suggester = self.services.suggester

        self._buffer = ""  # Latin letters of the word being typed
        self._local = []  # candidates from the dictionaries and the phonetic rules
        self._learned = []  # words the user picked before for this buffer
        self._claude_words = []  # candidates from Claude for the current buffer
        self._candidates = []  # what the popup shows, in order
        self._ghost = ""  # inline completion shown after the cursor
        self._ghost_context = ""  # the context Claude saw for that completion
        self._context = ""  # text recently typed into this input field
        self._caps = 0  # what the app supports (IBus.Capabilite flags)
        # The text before the cursor as the app shared it when the last key was pressed,
        # and what it should be after that key (see context.before_cursor). None: unknown.
        self._shared_base = None
        self._expected = None
        self._password = False
        self._generation = 0  # bumped on every change so stale Claude replies are dropped
        self._debounce_id = 0
        self._waiting = False
        self._cursor_moved = False

        self._table = IBus.LookupTable.new(PAGE_SIZE, 0, True, False)
        self._table.set_orientation(IBus.Orientation.VERTICAL)

        self._prop_claude = self._make_toggle("claude", "Claude suggestion", "claude_enabled")
        self._prop_inline = self._make_toggle("inline", "Inline completion (Tab)", "inline_completion")
        self._props = IBus.PropList()
        self._props.append(self._prop_claude)
        self._props.append(self._prop_inline)

    # ----- keys -----

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK or keyval in MODIFIER_KEYS:
            return False
        if self._password:
            return False
        # Apps refresh the text they share right before each key: start from that.
        self._shared_base = self._expected = self._shared_before_cursor()
        if state & SHORTCUT_MASK:
            # Ctrl/Alt/Super shortcuts belong to the application: finish the word first.
            self._dismiss_ghost()
            self._commit_selected()
            self._lose_track()
            return False

        if self._ghost and keyval == IBus.KEY_Tab:
            self._accept_ghost()
            return True
        if self._ghost and keyval == IBus.KEY_Escape:
            self._dismiss_ghost()
            return True
        if self._ghost.startswith(" ") and keyval == IBus.KEY_space and not self._buffer:
            # Typing the space the suggestion starts with keeps the rest of it on screen.
            rest = self._ghost[1:]
            self._commit_raw(" ")
            self._ghost = rest
            self._refresh_ui()
            if not rest:
                self._schedule_prediction()
            return True
        self._dismiss_ghost()

        ch = chr(keyval) if 0x20 <= keyval < 0x7F else ""
        if ch.isalpha() or (self._buffer and ch and ch in "`^:"):
            self._buffer += ch
            self._on_buffer_changed()
            return True
        if self._buffer:
            return self._key_while_composing(keyval, ch)
        return self._key_while_idle(keyval, ch)

    def _key_while_composing(self, keyval, ch):
        if keyval == IBus.KEY_BackSpace:
            self._buffer = self._buffer[:-1]
            if self._buffer:
                self._on_buffer_changed()
            else:
                self._invalidate()
                self._clear_composition()
                self._schedule_prediction()
            return True
        if keyval == IBus.KEY_Escape:
            # Keep the Latin letters as typed (handy for an English word).
            self._commit_raw(self._buffer)
            self._schedule_prediction()
            return True
        if keyval == IBus.KEY_space:
            self._commit(self._selected_word(), " ")
            self._schedule_prediction()
            return True
        if IBus.KEY_1 <= keyval <= IBus.KEY_9:
            index = self._page_start() + keyval - IBus.KEY_1
            if index < len(self._candidates):
                self._commit(self._candidates[index])
                self._schedule_prediction()
            return True
        moves = {
            IBus.KEY_Down: self._table.cursor_down,
            IBus.KEY_Up: self._table.cursor_up,
            IBus.KEY_Page_Down: self._table.page_down,
            IBus.KEY_Page_Up: self._table.page_up,
        }
        if keyval in moves:
            if moves[keyval]():
                self._after_cursor_move()
            return True
        if ch:
            # Punctuation or a digit ends the word.
            word = self._selected_word()
            self._commit(word, self._convert_symbol(ch, word))
            self._schedule_prediction()
            return True
        # Enter, Tab, arrows and other keys: finish the word, then let the app handle the key.
        self._commit(self._selected_word())
        if keyval in ENTER_KEYS:
            self._remember("\n")
        else:
            self._lose_track()
        return False

    def _key_while_idle(self, keyval, ch):
        if ch:
            converted = self._convert_symbol(ch, self._text_before_cursor())
            if converted != ch:
                self._commit_raw(converted)
            else:
                self._invalidate()
                self._remember(ch)  # the app types this character itself
            self._schedule_prediction()
            return converted != ch
        self._invalidate()
        if keyval == IBus.KEY_BackSpace:
            self._context = self._context[:-1]
            if self._expected is not None:
                self._expected = self._expected[:-1]
            self._schedule_prediction()
        elif keyval in ENTER_KEYS:
            self._remember("\n")
        else:
            self._lose_track()
        return False

    def _lose_track(self):
        """The cursor may have moved: what we know about the text before it is no longer valid."""
        self._context = ""
        self._shared_base = self._expected = None

    def _convert_symbol(self, ch, before):
        if ch == "." and self._config["dari_for_period"] and not before[-1:].isdigit():
            return "।"
        if ch.isdigit() and self._config["bangla_digits"]:
            return ch.translate(BANGLA_DIGITS)
        return ch

    # ----- candidates -----

    def _on_buffer_changed(self):
        self._invalidate()
        self._claude_words = []
        self._cursor_moved = False
        roman = self._buffer
        self._learned = self._userdict.exact(roman)
        self._local = _unique(
            self._learned
            + self._dictionary.candidates(roman)
            + self._userdict.completions(roman)
        )
        self._rebuild_candidates()
        self._refresh_ui()
        self._schedule_claude()

    def _rebuild_candidates(self):
        previous = self._selected_word() if self._cursor_moved else None
        # The local default stays first so Space is predictable; Claude's words come next.
        self._candidates = _unique(self._local[:1] + self._claude_words + self._local[1:])
        claude = set(self._claude_words)
        self._table.clear()
        for word in self._candidates:
            label = word + CLAUDE_MARK if word in claude else word
            self._table.append_candidate(IBus.Text.new_from_string(label))
        cursor = 0
        if previous in self._candidates:
            cursor = self._candidates.index(previous)
        elif self._config["auto_select_claude"] and self._claude_words and not self._learned:
            # Claude's best guess, unless the user already taught us what these letters mean.
            cursor = self._candidates.index(self._claude_words[0])
        self._table.set_cursor_pos(cursor)

    def _selected_word(self):
        if not self._candidates:
            return phonetic.transliterate(self._buffer) if self._buffer else ""
        pos = self._table.get_cursor_pos()
        return self._candidates[pos] if pos < len(self._candidates) else self._candidates[0]

    def _page_start(self):
        pos = self._table.get_cursor_pos()
        return pos - pos % PAGE_SIZE

    def _after_cursor_move(self):
        self._cursor_moved = True
        self._refresh_ui()

    # ----- Claude -----

    def _claude_on(self):
        return self._config["claude_enabled"] and not self._password

    def _schedule_claude(self):
        if self._claude_on() and self._buffer:
            self._start_timer()

    def _schedule_prediction(self, only_at_line_end=False):
        """Ask Claude, after the usual pause, how the text before the cursor goes on."""
        if not (self._claude_on() and self._config["inline_completion"]):
            return
        if only_at_line_end:
            # After a click: suggest only where a completion fits, not in the middle of text.
            shared = self._read_surrounding()
            if shared is None or not at_line_end(*shared):
                return
        context = self._text_before_cursor()
        if len(context.split()) < self._config["min_prediction_words"]:
            return
        if not phonetic.has_bangla(context):
            return
        self._start_timer()

    def _start_timer(self):
        self._cancel_timer()
        self._debounce_id = GLib.timeout_add(self._config["debounce_ms"], self._ask_claude, self._generation)

    def _cancel_timer(self):
        if self._debounce_id:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = 0

    def _ask_claude(self, generation):
        self._debounce_id = 0
        if generation == self._generation:
            roman = self._buffer
            context = self._prediction_context()
            self._waiting = self._suggester.request(
                context, roman, lambda result: self._on_suggestion(generation, roman, context, result)
            )
            self._refresh_ui()
        return GLib.SOURCE_REMOVE

    def _on_suggestion(self, generation, roman, context, result):
        if generation != self._generation:
            return  # the user kept typing; this answer is stale
        self._waiting = False
        if result is not None and self._claude_on():
            if roman:
                self._claude_words = result.words
                self._rebuild_candidates()
            if self._config["inline_completion"] and result.completion:
                ghost = result.completion
                if not roman and context[-1:].isspace():
                    ghost = ghost.lstrip()
                self._ghost = ghost
                self._ghost_context = context
        self._refresh_ui()

    def _invalidate(self):
        self._generation += 1
        self._cancel_timer()
        self._waiting = False

    # ----- text before the cursor -----

    def _read_surrounding(self):
        """(text, cursor) as the app shares it, or None if it shares nothing (or that is off)."""
        if not self._config["context_from_app"] or not self._caps & IBus.Capabilite.SURROUNDING_TEXT:
            return None
        result = self.get_surrounding_text()
        ibus_text, cursor = result[0], result[1]
        text = ibus_text.get_text() if ibus_text is not None else ""
        if not 0 <= cursor <= len(text):
            return None
        return text, cursor

    def _shared_before_cursor(self):
        shared = self._read_surrounding()
        if shared is None:
            return None
        text, cursor = shared
        return text[:cursor][-CONTEXT_KEEP:]

    def _text_before_cursor(self):
        return before_cursor(self._shared_before_cursor(), self._shared_base, self._expected, self._context)

    def _prediction_context(self):
        """What Claude gets as context: the end of the text before the cursor."""
        return self._text_before_cursor()[-self._config["context_chars"]:]

    # ----- inline completion -----

    def _accept_ghost(self):
        ghost = self._ghost
        self._ghost = ""
        if self._buffer:
            self._commit(self._selected_word(), ghost)
        else:
            self._commit_raw(ghost)
        self._schedule_prediction()  # and what comes after that

    def _dismiss_ghost(self):
        if self._ghost:
            self._ghost = ""
            self._refresh_ui()

    # ----- committing -----

    def _commit(self, word, suffix=""):
        """Commit the composed word (remembering the choice) plus an optional suffix."""
        if word and self._buffer:
            self._userdict.learn(self._buffer, word)
            self.services.schedule_save()
        self._commit_raw(word + suffix)

    def _commit_selected(self):
        if self._buffer:
            self._commit(self._selected_word())

    def _commit_raw(self, text):
        self._invalidate()
        if text:
            self.commit_text(IBus.Text.new_from_string(text))
            self._remember(text)
        self._clear_composition()

    def _remember(self, text):
        self._context = (self._context + text)[-CONTEXT_KEEP:]
        if self._expected is not None:
            self._expected += text

    def _clear_composition(self):
        self._buffer = ""
        self._local = []
        self._learned = []
        self._claude_words = []
        self._candidates = []
        self._ghost = ""
        self._cursor_moved = False
        self._table.clear()
        self._refresh_ui()

    # ----- UI -----

    def _refresh_ui(self):
        word = self._selected_word() if self._buffer else ""
        text = word + self._ghost
        ibus_text = IBus.Text.new_from_string(text)
        if text:
            attrs = IBus.AttrList()
            if word:
                attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, len(word)))
            if self._ghost:
                start, end = len(word), len(text)
                attrs.append(IBus.Attribute.new(IBus.AttrType.FOREGROUND, GHOST_COLOR, start, end))
                # Tells apps that understand hints to style this as a prediction.
                attrs.append(IBus.Attribute.new(IBus.AttrType.HINT, IBus.AttrPreedit.PREDICTION, start, end))
            ibus_text.set_attributes(attrs)
        # While an inline completion is shown, losing focus must not commit it.
        mode = IBus.PreeditFocusMode.CLEAR if self._ghost else IBus.PreeditFocusMode.COMMIT
        self.update_preedit_text_with_mode(ibus_text, len(word), bool(text), mode)

        if self._buffer and self._candidates:
            self.update_lookup_table(self._table, True)
        else:
            self.hide_lookup_table()

        aux = self._aux_text()
        if aux:
            self.update_auxiliary_text(IBus.Text.new_from_string(aux), True)
        else:
            self.hide_auxiliary_text()

    def _aux_text(self):
        if not self._buffer:
            return ""
        parts = [self._buffer]
        if self._waiting:
            parts.append("✦ …")
        elif self._ghost:
            parts.append("Tab ⇥")
        hint = STATUS_HINTS.get(self._suggester.status) if self._claude_on() else None
        if hint:
            parts.append(hint)
        return "   ".join(parts)

    # ----- IBus callbacks -----

    def do_set_capabilities(self, caps):
        self._caps = caps

    def do_enable(self):
        # Asking once tells the app we use its text, so it keeps sending it.
        self.get_surrounding_text()

    def do_focus_in(self):
        self._prop_claude.set_state(self._state_for("claude_enabled"))
        self._prop_inline.set_state(self._state_for("inline_completion"))
        self.register_properties(self._props)
        self.get_surrounding_text()

    def do_focus_out(self):
        if self._ghost and self._buffer:
            # The preedit was in CLEAR mode, so keep the typed word ourselves.
            self._ghost = ""
            self._commit(self._selected_word())
        self._forget()

    def do_reset(self):
        # Apps reset the input method when the cursor moves (a mouse click, for example).
        cleared_ghost = self._ghost_context if self._ghost else None
        self._forget()
        if cleared_ghost is not None and self._prediction_context() == cleared_ghost:
            return  # same place as the suggestion just cleared: do not bring it straight back
        self._schedule_prediction(only_at_line_end=True)

    def do_disable(self):
        self._forget()

    def _forget(self):
        self._invalidate()
        self._clear_composition()
        self._lose_track()

    def do_set_content_type(self, purpose, hints):
        self._password = purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN)
        if self._password:
            self._forget()

    def do_candidate_clicked(self, index, button, state):
        index += self._page_start()
        if index < len(self._candidates):
            self._commit(self._candidates[index])

    def do_page_up(self):
        if self._table.page_up():
            self._after_cursor_move()

    def do_page_down(self):
        if self._table.page_down():
            self._after_cursor_move()

    def do_cursor_up(self):
        if self._table.cursor_up():
            self._after_cursor_move()

    def do_cursor_down(self):
        if self._table.cursor_down():
            self._after_cursor_move()

    def do_property_activate(self, prop_name, state):
        toggles = {
            "claude": (self._prop_claude, "claude_enabled"),
            "inline": (self._prop_inline, "inline_completion"),
        }
        if prop_name not in toggles:
            return
        prop, key = toggles[prop_name]
        self._config[key] = state == IBus.PropState.CHECKED
        save_config(self._config)
        prop.set_state(state)
        self.update_property(prop)
        if not self._config[key]:
            self._invalidate()
            self._ghost = ""
            if key == "claude_enabled" and self._buffer:
                self._claude_words = []
                self._rebuild_candidates()
            self._refresh_ui()

    # ----- properties -----

    def _state_for(self, config_key):
        return IBus.PropState.CHECKED if self._config[config_key] else IBus.PropState.UNCHECKED

    def _make_toggle(self, key, label, config_key):
        return IBus.Property(
            key=key,
            prop_type=IBus.PropType.TOGGLE,
            label=IBus.Text.new_from_string(label),
            tooltip=IBus.Text.new_from_string(label),
            sensitive=True,
            visible=True,
            state=self._state_for(config_key),
        )
