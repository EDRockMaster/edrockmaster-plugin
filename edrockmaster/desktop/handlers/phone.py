"""The *Phone and tablet* section's calls (ADR 0055): the local server on or off, its port, a new
link. Each call answers with what the section shows then, the server already started or
stopped: binding a port is quick, and never done on the core's thread."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.phone import (
    PORTS,
    Phone,
    PhonePreferences,
    PhoneStore,
    new_key,
    phone_view,
)


class PhoneHandler:
    def __init__(self, context: CoreContext, *, store: PhoneStore, phone: Phone) -> None:
        self._context = context
        self._store = store
        self._phone = phone
        self._lock = threading.Lock()
        self._preferences = store.load()

    def start(self) -> None:
        """At start: listen if the player left it on."""
        if self._preferences.enabled:
            self._phone.apply(self._preferences)

    def phone(self) -> dict[str, Any]:
        return phone_view(self._preferences, self._phone.status, self._phone.addresses())

    def set_phone(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """``{"enabled": bool, "port": int}``; what is not valid is logged and changes nothing."""
        enabled, port = request.get("enabled"), request.get("port")
        if (
            not isinstance(enabled, bool)
            or not isinstance(port, int)
            or isinstance(port, bool)
            or port not in PORTS
        ):
            self._context.logger.warning("Phone and tablet refused: %r", dict(request))
            return self.phone()
        with self._lock:
            # The link key is drawn the first time the phone is turned on, then kept
            key = self._preferences.key or (new_key() if enabled else "")
            self._change(replace(self._preferences, enabled=enabled, port=port, key=key))
        return self.phone()

    def new_phone_link(self) -> dict[str, Any]:
        """Another link key: every device must scan the QR code again."""
        with self._lock:
            self._change(replace(self._preferences, key=new_key()))
        self._context.logger.info("Phone and tablet: new link, the devices must scan again")
        return self.phone()

    def use_phone_address(self, address: object) -> dict[str, Any]:
        """The QR code shows this address of the computer (ADR 0056); any other is refused."""
        if not isinstance(address, str) or address not in self._phone.addresses():
            self._context.logger.warning("Phone and tablet: not an address of this computer")
            return self.phone()
        with self._lock:
            self._change(replace(self._preferences, address=address))
        return self.phone()

    def _change(self, preferences: PhonePreferences) -> None:
        self._store.save(preferences)
        self._preferences = preferences
        self._phone.apply(preferences)
