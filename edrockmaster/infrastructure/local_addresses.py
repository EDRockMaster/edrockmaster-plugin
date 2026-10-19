"""The computer's addresses on the local network (ADR 0055, ADR 0056).

A home network is most often ``192.168.x.x``, sometimes ``172.16.x.x`` to ``172.31.x.x`` or
``10.x.x.x``; VPNs and virtual networks use the same ranges, mostly ``10.x.x.x`` (a WireGuard
VPN gives ``10.2.0.2``). The addresses are ordered by range in that order, then any other;
link-local and loopback addresses are left out. Within a range, the address towards the
internet comes first: the interface a connection to a public address would take, found by
"connecting" a UDP socket to such an address, which sends nothing. IPv4 only: a phone's camera
opens ``http://192.168.1.20:47800`` as is.
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


RANGES = tuple(
    ipaddress.ip_network(network) for network in ("192.168.0.0/16", "172.16.0.0/12", "10.0.0.0/8")
)
"""The private ranges of RFC 1918, in the order a home network most likely uses them."""


def local_addresses(
    resolve: Callable[[str], list[str]] | None = None,
    primary: Callable[[], str | None] = primary_address,
) -> list[str]:
    """The computer's local IPv4 addresses, the home network's most likely first."""
    first = primary()
    found = {*(resolve or _resolve)(socket.gethostname()), *([first] if first else [])}

    def rank(address: str) -> tuple[int, bool, ipaddress.IPv4Address]:
        parsed = ipaddress.IPv4Address(address)
        in_range = next((n for n, network in enumerate(RANGES) if parsed in network), len(RANGES))
        return in_range, address != first, parsed

    return sorted((address for address in found if _local(address)), key=rank)


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except OSError:
        return []
    return [str(info[4][0]) for info in infos]


def _local(address: str) -> bool:
    try:
        parsed = ipaddress.IPv4Address(address)
    except ValueError:
        return False
    return not (parsed.is_loopback or parsed.is_unspecified or parsed.is_link_local)
