"""A polite HTTP client for one community source (ADR 0039).

One request at a time, at least ``interval`` seconds apart; a ``429`` or a
``5xx`` makes the source busy for its ``Retry-After``, or 30 seconds doubled
up to 10 minutes. Every request says who asks (``user_agent``). It runs on the
I/O thread, which runs one job at a time: no lock is needed.
"""

from __future__ import annotations

import gzip
import json
import platform
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from email.message import Message
from typing import Any, Protocol

from edrockmaster.application.build import BuildInfo
from edrockmaster.application.community import Unavailable

SITE = "https://edrm.space"
INTERVAL = 1.0
TIMEOUT = 15.0
FIRST_BACKOFF = 30.0
LAST_BACKOFF = 600.0
_BUSY_STATUSES = frozenset({429, 500, 502, 503, 504})


class SourceError(Exception):
    """The source gave nothing: ``reason`` says why."""

    def __init__(self, reason: Unavailable, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


class _Response(Protocol):
    headers: Message

    def read(self) -> bytes: ...

    def __enter__(self) -> _Response: ...

    def __exit__(self, *exc_info: object) -> None: ...


type Opener = Callable[[urllib.request.Request, float], _Response]


def _open(request: urllib.request.Request, timeout: float) -> _Response:
    response: _Response = urllib.request.urlopen(request, timeout=timeout)
    return response


def user_agent(build: BuildInfo, system: str | None = None) -> str:
    """``EDRockMaster/<full version> (<channel>; <system> <version>) +https://edrm.space``."""
    system = system or f"{platform.system()} {platform.version()}".strip()
    return f"EDRockMaster/{build.version} ({build.channel.value}; {system}) +{SITE}"


class SourceClient:
    def __init__(  # noqa: PLR0913 - what it sends, and what the tests replace
        self,
        user_agent: str,
        *,
        opener: Opener = _open,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        interval: float = INTERVAL,
        timeout: float = TIMEOUT,
    ) -> None:
        self._user_agent = user_agent
        self._opener = opener
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._timeout = timeout
        self._last: float | None = None
        self._busy_until = 0.0
        self._backoff: float | None = None

    def get(self, url: str) -> Any:
        return self._send(urllib.request.Request(url, headers=self._headers()))

    def post(self, url: str, body: Mapping[str, Any]) -> Any:
        data = json.dumps(body).encode()
        headers = {**self._headers(), "Content-Type": "application/json"}
        return self._send(urllib.request.Request(url, data=data, headers=headers, method="POST"))

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }

    def _send(self, request: urllib.request.Request) -> Any:
        now = self._clock()
        if now < self._busy_until:
            raise SourceError(Unavailable.BUSY, f"busy for {self._busy_until - now:.0f} s more")
        if self._last is not None and (wait := self._last + self._interval - now) > 0:
            self._sleep(wait)
        try:
            with self._opener(request, self._timeout) as response:
                raw = response.read()
                encoding = response.headers.get("Content-Encoding", "")
        except urllib.error.HTTPError as error:
            self._last = self._clock()
            if error.code in _BUSY_STATUSES:
                self._wait_after(error.headers.get("Retry-After"))
                raise SourceError(Unavailable.BUSY, f"HTTP {error.code}") from error
            raise SourceError(Unavailable.DOWN, f"HTTP {error.code}") from error
        except (OSError, ValueError) as error:  # URLError, timeouts, a malformed address
            self._last = self._clock()
            raise SourceError(Unavailable.DOWN, str(error)) from error
        self._last = self._clock()
        self._backoff = None
        try:
            return json.loads(gzip.decompress(raw) if encoding == "gzip" else raw)
        except (OSError, ValueError) as error:  # a bad gzip stream, not JSON
            raise SourceError(Unavailable.DOWN, f"unreadable answer: {error}") from error

    def _wait_after(self, retry_after: str | None) -> None:
        try:
            delay = float(retry_after) if retry_after else None
        except ValueError:
            delay = None
        if delay is None:
            delay = FIRST_BACKOFF if self._backoff is None else self._backoff * 2
            delay = min(delay, LAST_BACKOFF)
            self._backoff = delay
        self._busy_until = self._clock() + delay
