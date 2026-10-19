"""The computer's addresses on the local network (ADR 0055).

The address shown in the QR code is the one of the network that leads to the internet: the
interface a connection to a public address would take. A UDP socket is "connected" to such
an address, which sends nothing, and gives its own. The others are listed for a computer on
several networks. IPv4 only: a phone's camera opens ``http://192.168.1.20:47800`` as is.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable

PUBLIC = ("192.0.2.1", 9)
"""An address of the documentation range (RFC 5737): nothing is ever sent to it."""


def primary_address(new_socket: Callable[[], socket.socket] | None = None) -> str | None:
    """The address towards the internet; ``None`` without a network."""
    opened = new_socket() if new_socket else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with opened:
            opened.connect(PUBLIC)
            address = str(opened.getsockname()[0])
    except OSError:
        return None
    return address if _local(address) else None


def local_addresses(
    resolve: Callable[[str], list[str]] | None = None,
    primary: Callable[[], str | None] = primary_address,
) -> list[str]:
    """The computer's local IPv4 addresses, the primary one first, without the loopback."""
    found = (resolve or _resolve)(socket.gethostname())
    first = primary()
    ordered = [first] if first else []
    ordered += sorted({address for address in found if _local(address)} - set(ordered))
    return ordered


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except OSError:
        return []
    return [str(info[4][0]) for info in infos]


def _local(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not parsed.is_loopback and not parsed.is_unspecified
