"""The local server, on a real socket of the loopback (ADR 0055)."""

import http.client
import json
import logging
import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from edrockmaster.infrastructure.local_addresses import local_addresses, primary_address
from edrockmaster.infrastructure.local_server import COOKIE, TRANSPORT_MARK, LocalServer

PAGE = "<!doctype html><html><head><title>EDRockMaster</title></head><body></body></html>"


class Site:
    def __init__(self) -> None:
        self.key = "k" * 22
        self.calls: list[tuple[str, list[Any]]] = []
        self.server = LocalServer(
            port=0,
            key=lambda: self.key,
            page=lambda: PAGE,
            call=self.call,
            hosts=lambda: ["192.168.1.20"],
            logger=logging.getLogger("test.local_server"),
            bind="127.0.0.1",
        )

    def call(self, name: str, arguments: list[Any]) -> Any:
        if name == "boom":
            raise RuntimeError("boom")
        if name not in ("settings", "reset"):
            raise KeyError(name)
        self.calls.append((name, arguments))
        return {"language": "fr"} if name == "settings" else None

    def request(
        self,
        method: str,
        path: str,
        *,
        cookie: str | None = None,
        host: str | None = None,
        body: bytes | None = None,
    ) -> http.client.HTTPResponse:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{self.server.port}"}
        if cookie is not None:
            headers["Cookie"] = f"{COOKIE}={cookie}"
        connection.request(method, path, body=body, headers=headers)
        return connection.getresponse()


@pytest.fixture
def site() -> Iterator[Site]:
    started = Site()
    started.server.start()
    yield started
    started.server.stop()


def test_the_link_gives_a_cookie_then_the_page(site: Site) -> None:
    answer = site.request("GET", f"/?key={site.key}")
    assert answer.status == 303
    assert answer.getheader("Location") == "/"
    cookie = answer.getheader("Set-Cookie") or ""
    assert cookie.startswith(f"{COOKIE}={site.key};")
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    page = site.request("GET", "/", cookie=site.key)
    assert page.status == 200
    # Marked, so that the interface talks over HTTP
    assert f"<head>{TRANSPORT_MARK}<title>" in page.read().decode()


@pytest.mark.parametrize("cookie", [None, "wrong", ""])
def test_without_the_key_the_device_is_asked_to_scan_again(site: Site, cookie: str | None) -> None:
    answer = site.request("GET", "/", cookie=cookie)
    assert answer.status == 403
    assert "Scan the QR code again" in answer.read().decode()
    assert site.request("GET", "/?key=wrong").status == 403
    assert site.request("POST", "/api/settings", cookie=cookie, body=b"{}").status == 403
    assert site.calls == []


def test_a_new_key_shuts_out_the_devices_already_connected(site: Site) -> None:
    old = site.key
    site.key = "n" * 22
    assert site.request("GET", "/", cookie=old).status == 403


def test_another_host_gets_nothing(site: Site) -> None:
    # A page elsewhere, its name pointed at the computer (DNS rebinding)
    answer = site.request("GET", "/", cookie=site.key, host=f"evil.example:{site.server.port}")
    assert answer.status == 421
    assert site.request("GET", "/", cookie=site.key, host="127.0.0.1:1").status == 421
    assert site.request("GET", "/", cookie=site.key, host=None).status == 200
    local = f"192.168.1.20:{site.server.port}"
    assert site.request("GET", "/", cookie=site.key, host=local).status == 200


def test_the_calls_of_the_interface(site: Site) -> None:
    answer = site.request(
        "POST", "/api/settings", cookie=site.key, body=json.dumps({"args": []}).encode()
    )
    assert answer.status == 200
    assert json.loads(answer.read()) == {"language": "fr"}
    answer = site.request("POST", "/api/reset", cookie=site.key, body=b'{"args": ["mining"]}')
    assert (answer.status, answer.read()) == (200, b"null")
    assert site.calls == [("settings", []), ("reset", ["mining"])]


@pytest.mark.parametrize(
    ("path", "body", "status"),
    [
        ("/api/open_folder", b"{}", 404),
        ("/api/reset", b"not json", 400),
        ("/api/reset", b'{"args": "mining"}', 400),
        ("/api/boom", b"{}", 500),
    ],
)
def test_refused_calls(site: Site, path: str, body: bytes, status: int) -> None:
    assert site.request("POST", path, cookie=site.key, body=body).status == status


def test_the_live_view_as_events(site: Site) -> None:
    site.server.publish({"version": 1, "current": "mining"})
    answer = site.request("GET", "/events", cookie=site.key)
    assert answer.status == 200
    assert answer.getheader("Content-Type") == "text/event-stream; charset=utf-8"
    # The last view at once, then the next one pushed
    assert answer.readline() == b'data: {"version": 1, "current": "mining"}\n'
    assert answer.readline() == b"\n"
    site.server.publish({"version": 1, "current": "trade"})
    assert json.loads(answer.readline().removeprefix(b"data: ")) == {
        "version": 1,
        "current": "trade",
    }


def test_stopping_ends_the_events_and_closes_the_port(site: Site) -> None:
    port = site.server.port
    answer = site.request("GET", "/events", cookie=site.key)
    ended = threading.Event()

    def read_to_the_end() -> None:
        answer.read()
        ended.set()

    threading.Thread(target=read_to_the_end, daemon=True).start()
    site.server.stop()
    assert ended.wait(5)
    with (
        pytest.raises(ConnectionRefusedError),
        socket.create_connection(("127.0.0.1", port), timeout=1),
    ):
        pass


def test_a_port_already_held_is_refused() -> None:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        server = LocalServer(
            port=held.getsockname()[1],
            key=lambda: "k",
            page=lambda: PAGE,
            call=lambda name, arguments: None,
            hosts=list,
            logger=logging.getLogger("test.local_server"),
            bind="127.0.0.1",
        )
        # Linux says "Address already in use", Windows "Only one usage of each socket address"
        with pytest.raises(OSError, match=r"in use|Only one usage"):
            server.start()


# --- the computer's addresses ---------------------------------------------------------------


def test_the_primary_address_comes_first_without_the_loopback() -> None:
    addresses = local_addresses(
        resolve=lambda host: ["127.0.1.1", "10.0.0.5", "192.168.1.20", "10.0.0.5"],
        primary=lambda: "192.168.1.20",
    )
    assert addresses == ["192.168.1.20", "10.0.0.5"]


def test_without_a_network_no_primary_address() -> None:
    class Offline(socket.socket):
        def connect(self, address: Any) -> None:
            raise OSError("network unreachable")

    assert primary_address(lambda: Offline(socket.AF_INET, socket.SOCK_DGRAM)) is None
    assert local_addresses(resolve=lambda host: [], primary=lambda: None) == []
