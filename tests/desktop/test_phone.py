"""The phone and tablet (ADR 0055): the local server as the player wants it, and what the
*Phone and tablet* section shows."""

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

import jsonschema
import pytest

from edrockmaster.desktop.handlers.phone import PhoneHandler
from edrockmaster.desktop.phone import (
    DEFAULT_PORT,
    Phone,
    PhonePreferences,
    PhoneStatus,
    PhoneStore,
    phone_view,
    remote_calls,
)
from edrockmaster.desktop.window import WINDOW_ONLY, InterfaceApi
from tests.desktop.handlers.fake_core import FakeCore
from tests.desktop.schemas import LIVE_VIEW_SCHEMA
from tests.fakes import FakeConfig

SCHEMA = json.loads((LIVE_VIEW_SCHEMA.parent / "phone.schema.json").read_text(encoding="utf-8"))


class FakeServer:
    """Stands for ``LocalServer``: records what it is asked."""

    taken: ClassVar[set[int]] = set()

    def __init__(self, *, port: int, **parts: Any) -> None:
        self.port = port
        self.parts = parts
        self.running = False
        self.published: list[Any] = []

    def start(self) -> None:
        if self.port in FakeServer.taken:
            raise OSError("Address already in use")
        self.running = True

    def stop(self) -> None:
        self.running = False

    def publish(self, view: Any) -> None:
        self.published.append(view)


class Harness:
    def __init__(self) -> None:
        self.servers: list[FakeServer] = []
        self.config = FakeConfig()
        self.phone = Phone(
            call=lambda name, arguments: None,
            page=lambda: "<html><head></head></html>",
            logger=logging.getLogger("test.phone"),
            addresses=lambda: ["192.168.1.20", "10.0.0.5"],
            server=self.server,
        )
        self.core = FakeCore()
        self.handler = PhoneHandler(
            self.core.context, store=PhoneStore(self.config), phone=self.phone
        )

    def server(self, **parts: Any) -> FakeServer:
        made = FakeServer(**parts)
        self.servers.append(made)
        return made


@pytest.fixture
def harness() -> Harness:
    FakeServer.taken = set()
    return Harness()


def test_off_by_default_nothing_listens(harness: Harness) -> None:
    harness.handler.start()
    shown = harness.handler.phone()
    assert shown == {
        "enabled": False,
        "port": DEFAULT_PORT,
        "listening": False,
        "error": None,
        "link": None,
        "qr": None,
        "otherLinks": [],
    }
    assert harness.servers == []
    jsonschema.validate(shown, SCHEMA)


def test_turned_on_it_listens_and_shows_its_link(harness: Harness) -> None:
    shown = harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    [server] = harness.servers
    assert server.running
    key = harness.config.get_str("edrockmaster.desktop.phone_key")
    assert key is not None
    assert len(key) >= 22  # 128 bits
    assert shown["link"] == f"http://192.168.1.20:47800/?key={key}"
    assert shown["otherLinks"] == [
        {"address": "10.0.0.5", "link": f"http://10.0.0.5:47800/?key={key}"}
    ]
    assert shown["qr"].startswith("<svg")
    assert server.parts["key"]() == key
    jsonschema.validate(shown, SCHEMA)


def test_turned_off_it_stops_and_the_key_stays(harness: Harness) -> None:
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    key = harness.config.get_str("edrockmaster.desktop.phone_key")
    shown = harness.handler.set_phone({"enabled": False, "port": DEFAULT_PORT})
    assert not harness.servers[0].running
    assert (shown["listening"], shown["link"]) == (False, None)
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    assert harness.config.get_str("edrockmaster.desktop.phone_key") == key


def test_another_port_starts_it_again(harness: Harness) -> None:
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    shown = harness.handler.set_phone({"enabled": True, "port": 48000})
    first, second = harness.servers
    assert (first.running, second.running, second.port) == (False, True, 48000)
    assert ":48000/" in shown["link"]


def test_a_port_held_by_another_application_says_so(harness: Harness) -> None:
    FakeServer.taken = {DEFAULT_PORT}
    shown = harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    assert (shown["listening"], shown["error"], shown["link"]) == (False, "portInUse", None)
    jsonschema.validate(shown, SCHEMA)


def test_a_new_link_shuts_out_the_devices(harness: Harness) -> None:
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    server = harness.servers[0]
    old = server.parts["key"]()
    shown = harness.handler.new_phone_link()
    assert server.parts["key"]() != old
    assert old not in shown["link"]
    assert server.running  # the same server: only the key changed


@pytest.mark.parametrize(
    "request_",
    [{"enabled": "yes", "port": DEFAULT_PORT}, {"enabled": True, "port": 80}, {"enabled": True}],
)
def test_invalid_requests_change_nothing(harness: Harness, request_: dict[str, Any]) -> None:
    assert not harness.handler.set_phone(request_)["enabled"]
    assert harness.servers == []


def test_left_on_it_listens_at_the_next_start(harness: Harness) -> None:
    harness.handler.set_phone({"enabled": True, "port": 48000})
    later = Harness()
    later.config = harness.config
    later.handler = PhoneHandler(
        FakeCore().context, store=PhoneStore(harness.config), phone=later.phone
    )
    later.handler.start()
    [server] = later.servers
    assert (server.running, server.port) == (True, 48000)


def test_the_views_reach_the_devices(harness: Harness) -> None:
    harness.phone.publish({"version": 1})  # nothing listens: nothing to do
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    harness.phone.publish({"version": 1})
    assert harness.servers[0].published == [{"version": 1}]


def test_a_server_started_gets_the_current_view_at_once(harness: Harness) -> None:
    # A device scanning the QR code while the game writes nothing must not wait for its next
    # event: the view is pushed again as soon as the server listens
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    assert harness.core.refreshes == 1
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})  # already listening
    harness.handler.set_phone({"enabled": True, "port": 48000})  # another server
    assert harness.core.refreshes == 2
    harness.handler.set_phone({"enabled": False, "port": 48000})
    assert harness.core.refreshes == 2


def test_the_player_chooses_the_address_of_the_qr_code(harness: Harness) -> None:
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    shown = harness.handler.use_phone_address("10.0.0.5")
    assert shown["link"].startswith("http://10.0.0.5:47800/")
    assert [other["address"] for other in shown["otherLinks"]] == ["192.168.1.20"]
    assert harness.config.get_str("edrockmaster.desktop.phone_address") == "10.0.0.5"
    # Turned off and on, the choice stays
    harness.handler.set_phone({"enabled": False, "port": DEFAULT_PORT})
    shown = harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    assert shown["link"].startswith("http://10.0.0.5:47800/")


def test_an_address_chosen_and_gone_gives_way_to_the_most_likely() -> None:
    preferences = PhonePreferences(True, DEFAULT_PORT, "k", address="192.168.0.9")
    shown = phone_view(preferences, PhoneStatus(listening=True), ["192.168.1.20", "10.2.0.2"])
    assert shown["link"] == "http://192.168.1.20:47800/?key=k"


@pytest.mark.parametrize("address", ["8.8.8.8", 3, None])
def test_an_address_not_of_this_computer_is_refused(harness: Harness, address: object) -> None:
    harness.handler.set_phone({"enabled": True, "port": DEFAULT_PORT})
    shown = harness.handler.use_phone_address(address)
    assert shown["link"].startswith("http://192.168.1.20:")
    assert harness.config.get_str("edrockmaster.desktop.phone_address") == ""


def test_stored_preferences_fall_back_when_invalid() -> None:
    config = FakeConfig()
    config.values["edrockmaster.desktop.phone_port"] = "80"
    assert PhoneStore(config).load() == PhonePreferences()
    config.values["edrockmaster.desktop.phone_port"] = "not a port"
    assert PhoneStore(config).load().port == DEFAULT_PORT


def test_without_a_network_address_no_link() -> None:
    shown = phone_view(PhonePreferences(True, DEFAULT_PORT, "k"), PhoneStatus(listening=True), [])
    assert (shown["listening"], shown["link"], shown["qr"]) == (True, None, None)


def test_a_device_makes_the_window_s_calls_except_those_on_the_computer() -> None:
    calls = remote_calls(InterfaceApi, WINDOW_ONLY)
    assert {"ready", "settings", "save_settings", "add_goal", "set_phone"} <= calls
    assert not calls & {"open_folder", "restart_to_update"}
    assert not any(name.startswith("_") for name in calls)


def test_the_schema_of_the_section_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert Path(LIVE_VIEW_SCHEMA.parent / "phone.schema.json").is_file()
