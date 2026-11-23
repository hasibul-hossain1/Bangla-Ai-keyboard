"""Connects to the IBus daemon and serves the Bangla AI engine."""

import logging
import signal
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, GObject, IBus

from .claude import Suggester
from .config import USER_DICT_FILE, VERSION, load_config
from .dictionary import Dictionary
from .engine import BanglaAIEngine
from .userdict import UserDict

log = logging.getLogger(__name__)

COMPONENT_NAME = "org.freedesktop.IBus.BanglaAI"
ENGINE_NAME = "bangla-ai"
SAVE_DELAY_SECONDS = 5


class Services:
    """State shared by every engine instance (one instance per input field)."""

    def __init__(self):
        self.config = load_config()
        self.userdict = UserDict(USER_DICT_FILE)
        self.dictionary = Dictionary.load()
        self.suggester = Suggester(self.config)
        self._save_id = 0

    def schedule_save(self):
        if not self._save_id:
            self._save_id = GLib.timeout_add_seconds(SAVE_DELAY_SECONDS, self._save)

    def _save(self):
        self._save_id = 0
        self.userdict.save()
        return GLib.SOURCE_REMOVE

    def shutdown(self):
        if self._save_id:
            GLib.source_remove(self._save_id)
            self._save_id = 0
        self.userdict.save()
        self.suggester.shutdown()


def run(exec_by_ibus):
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        log.error("Could not connect to the IBus daemon")
        sys.exit(1)

    services = Services()
    BanglaAIEngine.services = services
    mainloop = GLib.MainLoop()

    def quit_mainloop(*_args):
        mainloop.quit()
        return GLib.SOURCE_REMOVE

    bus.connect("disconnected", quit_mainloop)
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, quit_mainloop)

    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine(ENGINE_NAME, GObject.type_from_name("BanglaAIEngine"))

    if exec_by_ibus:
        bus.request_name(COMPONENT_NAME, 0)
    else:
        # Debug mode: register ourselves and switch to the engine right away.
        component = IBus.Component.new(
            COMPONENT_NAME, "Bangla AI input method", VERSION, "MIT",
            "hasibul-hossain1", "https://github.com/hasibul-hossain1/Bangla-Ai-keyboard", "", "bangla-ai-ime",
        )
        component.add_engine(IBus.EngineDesc.new(
            ENGINE_NAME, "Bangla AI (debug)", "Phonetic Bangla with Claude suggestions",
            "bn", "MIT", "hasibul-hossain1", "", "us",
        ))
        bus.register_component(component)
        bus.set_global_engine_async(ENGINE_NAME, -1, None, None, None)

    log.info("Bangla AI engine started (model %s)", services.config["model"])
    try:
        mainloop.run()
    finally:
        services.shutdown()
        log.info("Bangla AI engine stopped")
