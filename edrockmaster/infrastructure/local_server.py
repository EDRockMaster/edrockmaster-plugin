"""The application on a phone or a tablet, from the local network (ADR 0055).

An HTTP server of the standard library, on threads of its own, serves the interface's page,
its calls and the live view to the devices of the home network:

- ``GET /?key=<link key>``: the link of the QR code; gives the device a cookie holding the
  key, then sends it to ``/``;
- ``GET /``: the interface's page, marked so that it talks over HTTP;
- ``POST /api/<call>``: one of the interface's calls, its arguments a JSON list
  (``{"args": [...]}``), its result as JSON;
- ``GET /events``: the live view, as server-sent events: the last one at once, then each one
  the core pushes.

Without the cookie, a request gets only a page asking to scan the QR code again; a ``Host``
that is not one of the computer's addresses gets nothing (DNS rebinding). No HTTPS: a
certificate for a local address would warn on every device.
"""

from __future__ import annotations

import hmac
import json
import logging
import queue
import sys
import threading
from collections.abc import Callable, Collection, Mapping
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

THREAD_NAME = "EDRockMaster local server"
COOKIE = "edrm_key"
COOKIE_SECONDS = 365 * 24 * 60 * 60
KEEP_ALIVE_SECONDS = 15.0
"""A comment line on the events stream, so that a device or a router never drops it idle."""
TRANSPORT_MARK = '<meta name="edrm-transport" content="http">'
MAX_BODY = 1_000_000
POLL_SECONDS = 0.1
"""How often the server looks whether it is asked to stop."""

SCAN_AGAIN = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>EDRockMaster</title>
<body style="font-family:sans-serif;background:#0d0f12;color:#e6e6e6;padding:1.5rem">
<h1>EDRockMaster</h1>
<p>Scan the QR code again: <i>Settings</i>, <i>Phone and tablet</i>, in the application.</p>
<p lang="fr">Scannez de nouveau le QR code : <i>Réglages</i>, <i>Téléphone et tablette</i>,
dans l'application.</p>
</body></html>
"""

type Call = Callable[[str, list[Any]], Any]
"""Runs a call of the interface by its name; ``KeyError`` for a call not offered."""


class LocalServer:
    def __init__(  # noqa: PLR0913 - what the server shows, to whom, and where
        self,
        *,
        port: int,
        key: Callable[[], str],
        page: Callable[[], str],
        call: Call,
        hosts: Callable[[], Collection[str]],
        logger: logging.Logger,
        bind: str = "0.0.0.0",
    ) -> None:
        """``key``: the link key in force; ``page``: the interface's page; ``hosts``: the
        computer's addresses, without the port."""
        self._port = port
        self._key = key
        self._page = page
        self._call = call
        self._hosts = hosts
        self._logger = logger
        self._bind = bind
        self._server: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()
        self._streams: list[queue.Queue[str | None]] = []
        self._last: str | None = None

    @property
    def port(self) -> int:
        """The port listened on: the one asked, or the one the system gave for 0."""
        return self._server.server_address[1] if self._server else self._port

    def start(self) -> None:
        """Listen; ``OSError`` if the port cannot be had (another application holds it)."""
        server = _Server((self._bind, self._port), _Handler, self)
        self._server = server
        threading.Thread(
            target=server.serve_forever, args=(POLL_SECONDS,), name=THREAD_NAME, daemon=True
        ).start()
        self._logger.info("Phone and tablet: listening on port %d", self.port)

    def stop(self) -> None:
        server, self._server = self._server, None
        if server is None:
            return
        with self._lock:
            streams, self._streams = self._streams, []
        for stream in streams:
            stream.put(None)
        server.shutdown()
        server.server_close()
        self._logger.info("Phone and tablet: stopped")

    def publish(self, view: Mapping[str, Any]) -> None:
        """A live view the core pushes: to every device following the events. Never blocks."""
        event = json.dumps(view, ensure_ascii=False)
        with self._lock:
            self._last = event
            streams = list(self._streams)
        for stream in streams:
            stream.put(event)

    # What the request handler asks

    def page(self) -> str:
        """The interface's page, marked so that it talks over HTTP."""
        return self._page().replace("<head>", f"<head>{TRANSPORT_MARK}", 1)

    def call(self, name: str, arguments: list[Any]) -> Any:
        return self._call(name, arguments)

    def failed(self, name: str) -> None:
        self._logger.exception("Phone and tablet: the call %s failed", name)

    def allowed_host(self, host: str | None) -> bool:
        if not host:
            return False
        name, _, port = host.rpartition(":")
        if port != str(self.port):
            return False
        return name.strip("[]") in {*self._hosts(), "localhost", "127.0.0.1"}

    def valid_key(self, given: str | None) -> bool:
        key = self._key()
        return bool(given) and bool(key) and hmac.compare_digest(str(given), key)

    def follow(self) -> queue.Queue[str | None]:
        stream: queue.Queue[str | None] = queue.Queue()
        with self._lock:
            if self._last is not None:
                stream.put(self._last)
            self._streams.append(stream)
        return stream

    def unfollow(self, stream: queue.Queue[str | None]) -> None:
        with self._lock:
            if stream in self._streams:
                self._streams.remove(stream)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, SO_REUSEADDR lets a second socket take a port already listened on
    allow_reuse_address = sys.platform != "win32"

    def __init__(
        self, address: tuple[str, int], handler: type[_Handler], site: LocalServer
    ) -> None:
        self.site = site
        super().__init__(address, handler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        # A device that goes away (a closed page, a phone asleep) is no error
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    protocol_version = "HTTP/1.1"
    server_version = "EDRockMaster"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        pass  # each request is not worth a line of the application's log

    def do_GET(self) -> None:
        if not self._host_allowed():
            return
        url = urlsplit(self.path)
        if url.path == "/" and "key" in parse_qs(url.query):
            self._link(parse_qs(url.query)["key"][0])
        elif not self._cookie_valid():
            self._send(HTTPStatus.FORBIDDEN, "text/html; charset=utf-8", SCAN_AGAIN.encode())
        elif url.path == "/":
            page = self.server.site.page()
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", page.encode())
        elif url.path == "/events":
            self._events()
        else:
            self._send(HTTPStatus.NOT_FOUND, "text/plain", b"Not found")

    def do_POST(self) -> None:
        if not self._host_allowed():
            return
        if not self._cookie_valid():
            self._send(HTTPStatus.FORBIDDEN, "text/plain", b"Scan the QR code again")
            return
        name = urlsplit(self.path).path.removeprefix("/api/")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY:
                raise ValueError("body too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            arguments = body.get("args", []) if isinstance(body, dict) else None
            if not isinstance(arguments, list):
                raise ValueError("args is not a list")
        except ValueError as error:
            self._send(HTTPStatus.BAD_REQUEST, "text/plain", str(error).encode())
            return
        try:
            result = self.server.site.call(name, arguments)
        except KeyError:
            self._send(HTTPStatus.NOT_FOUND, "text/plain", b"No such call")
            return
        except Exception:
            self.server.site.failed(name)
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "text/plain", b"The call failed")
            return
        payload = json.dumps(result, ensure_ascii=False).encode()
        self._send(HTTPStatus.OK, "application/json", payload)

    def _host_allowed(self) -> bool:
        if self.server.site.allowed_host(self.headers.get("Host")):
            return True
        self._send(HTTPStatus.MISDIRECTED_REQUEST, "text/plain", b"Unknown host")
        return False

    def _cookie_valid(self) -> bool:
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        morsel = cookies.get(COOKIE)
        return self.server.site.valid_key(morsel.value if morsel else None)

    def _link(self, given: str) -> None:
        if not self.server.site.valid_key(given):
            self._send(HTTPStatus.FORBIDDEN, "text/html; charset=utf-8", SCAN_AGAIN.encode())
            return
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header(
            "Set-Cookie",
            f"{COOKIE}={given}; Max-Age={COOKIE_SECONDS}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.close_connection = True
        stream = self.server.site.follow()
        try:
            while True:
                try:
                    event = stream.get(timeout=KEEP_ALIVE_SECONDS)
                except queue.Empty:
                    self.wfile.write(b": still here\n\n")
                else:
                    if event is None:  # the server stops
                        return
                    self.wfile.write(f"data: {event}\n\n".encode())
                self.wfile.flush()
        except OSError:
            return  # the device went away
        finally:
            self.server.site.unfollow(stream)

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
