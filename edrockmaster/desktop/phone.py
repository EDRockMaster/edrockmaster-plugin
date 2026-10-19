"""The application on a phone or a tablet (ADR 0055): the local server, as the player wants it.

``PhonePreferences`` are kept in ``settings.json``, apart from the other settings: whether the
local server listens, on which port, the link key of the QR code, drawn the first time the
phone is turned on, and the address the player chose for it (ADR 0056). ``Phone`` starts the
server, stops it, starts it again on another port, and hands it each live view. Its link is
the address chosen while it is still the computer's, else the home network's most likely
(``local_addresses``), with the key. ``phone_view`` gives the *Phone and tablet* section what
it shows.
"""

from __future__ import annotations

import logging
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import segno

from edrockmaster.infrastructure.local_addresses import local_addresses
from edrockmaster.infrastructure.local_server import Call, LocalServer
from edrockmaster.infrastructure.settings_store import ConfigStore

DEFAULT_PORT = 47800
PORTS = range(1024, 65536)
"""Ports a player's application may listen on, without administrator rights."""
KEY_BYTES = 16
"""128 bits of the link key."""
KEY_ENABLED = "edrockmaster.desktop.phone"
KEY_PORT = "edrockmaster.desktop.phone_port"
KEY_LINK = "edrockmaster.desktop.phone_key"
KEY_ADDRESS = "edrockmaster.desktop.phone_address"


def new_key() -> str:
    return secrets.token_urlsafe(KEY_BYTES)


@dataclass(frozen=True, slots=True)
class PhonePreferences:
    enabled: bool = False
    port: int = DEFAULT_PORT
    key: str = ""
    """The link key of the QR code; empty until the phone is first turned on."""
    address: str = ""
    """The address the player chose for the QR code; empty: the most likely one."""


class PhoneStore:
    def __init__(self, config: ConfigStore) -> None:
        self._config = config

    def load(self) -> PhonePreferences:
        try:
            port = int(self._config.get_str(KEY_PORT, default="") or "")
        except ValueError:
            port = DEFAULT_PORT
        return PhonePreferences(
            enabled=self._config.get_bool(KEY_ENABLED, default=False),
            port=port if port in PORTS else DEFAULT_PORT,
            key=self._config.get_str(KEY_LINK, default="") or "",
            address=self._config.get_str(KEY_ADDRESS, default="") or "",
        )

    def save(self, preferences: PhonePreferences) -> None:
        self._config.set(KEY_ENABLED, preferences.enabled)
        self._config.set(KEY_PORT, str(preferences.port))
        self._config.set(KEY_LINK, preferences.key)
        self._config.set(KEY_ADDRESS, preferences.address)


class Server(Protocol):
    """What ``Phone`` asks of a ``LocalServer``."""

    @property
    def port(self) -> int: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def publish(self, view: Mapping[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class PhoneStatus:
    listening: bool = False
    error: str | None = None
    """``portInUse`` when another application holds the port."""


class Phone:
    """Called from the window's and the devices' threads: one change at a time."""

    def __init__(
        self,
        call: Call,
        page: Callable[[], str],
        logger: logging.Logger,
        addresses: Callable[[], list[str]] = local_addresses,
        server: Callable[..., Server] = LocalServer,
    ) -> None:
        """``call``: runs the interface's calls a device may make; ``page``: the interface."""
        self._call = call
        self._page = page
        self._logger = logger
        self._addresses = addresses
        self._new_server = server
        self._lock = threading.Lock()
        self._server: Server | None = None
        self._key = ""
        self._status = PhoneStatus()

    @property
    def status(self) -> PhoneStatus:
        return self._status

    def addresses(self) -> list[str]:
        return self._addresses()

    def apply(self, preferences: PhonePreferences) -> PhoneStatus:
        """Listen, or not, as the preferences say; a new key shuts out the devices at once."""
        with self._lock:
            self._key = preferences.key
            running = self._server
            if running is not None and (
                not preferences.enabled or running.port != preferences.port
            ):
                running.stop()
                self._server = None
            if not preferences.enabled:
                self._status = PhoneStatus()
            elif self._server is None:
                self._status = self._start(preferences.port)
            return self._status

    def publish(self, view: Mapping[str, Any]) -> None:
        server = self._server
        if server is not None:
            server.publish(view)

    def stop(self) -> None:
        self.apply(PhonePreferences(enabled=False, key=self._key))

    def _start(self, port: int) -> PhoneStatus:
        server = self._new_server(
            port=port,
            key=lambda: self._key,
            page=self._page,
            call=self._call,
            hosts=self._addresses,
            logger=self._logger,
        )
        try:
            server.start()
        except OSError as error:
            self._logger.warning("Phone and tablet: port %d not available: %s", port, error)
            return PhoneStatus(error="portInUse")
        self._server = server
        return PhoneStatus(listening=True)


def remote_calls(api: type, window_only: frozenset[str]) -> frozenset[str]:
    """The calls of the interface a device may make: the window's, except those that act on the
    computer itself."""
    return frozenset(
        name
        for name, value in vars(api).items()
        if callable(value) and not name.startswith("_") and name not in window_only
    )


def phone_view(
    preferences: PhonePreferences, status: PhoneStatus, addresses: Sequence[str]
) -> dict[str, Any]:
    """The *Phone and tablet* section of *Settings*, as ``phone.schema.json`` says: the address
    chosen first while it is still the computer's (ADR 0056)."""
    ordered = sorted(addresses, key=lambda address: address != preferences.address)
    links = [f"http://{address}:{preferences.port}/?key={preferences.key}" for address in ordered]
    link = links[0] if status.listening and links else None
    return {
        "enabled": preferences.enabled,
        "port": preferences.port,
        "listening": status.listening,
        "error": status.error,
        "link": link,
        # Dark on white, whatever the theme: what a camera reads best
        "qr": segno.make(link, error="m").svg_inline(scale=5, border=2, dark="#000", light="#fff")
        if link
        else None,
        "otherLinks": [
            {"address": address, "link": other}
            for address, other in zip(ordered[1:], links[1:], strict=True)
        ]
        if link
        else [],
    }
