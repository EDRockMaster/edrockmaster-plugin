"""The polite HTTP client of the community sources (ADR 0039), without network."""

import gzip
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from edrockmaster.application.build import BuildInfo, Channel
from edrockmaster.application.community import Unavailable
from edrockmaster.infrastructure.sources.http import SourceClient, SourceError, user_agent


class FakeResponse:
    def __init__(self, body: bytes, encoding: str = "") -> None:
        self._body = body
        self.headers = Message()
        if encoding:
            self.headers["Content-Encoding"] = encoding

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeSource:
    """Answers each request with the next item: a body, or an exception to raise."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, FakeResponse):
            return answer
        return FakeResponse(json.dumps(answer).encode())


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.org", code, "error", headers, None)


def client(source: FakeSource, clock: Clock) -> SourceClient:
    return SourceClient("EDRockMaster/test", opener=source, clock=clock, sleep=clock.sleep)


def test_the_user_agent_says_who_asks() -> None:
    build = BuildInfo("0.6.0-rc.1", Channel.CANDIDATE)
    assert user_agent(build, "Windows 10.0.19045") == (
        "EDRockMaster/0.6.0-rc.1 (candidate; Windows 10.0.19045) +https://edrm.space"
    )
    assert user_agent(build).startswith("EDRockMaster/0.6.0-rc.1 (candidate; ")


def test_a_get_and_a_post_say_who_asks_and_read_json() -> None:
    source, clock = FakeSource({"a": 1}, [2]), Clock()
    http = client(source, clock)
    assert http.get("https://example.org/get") == {"a": 1}
    assert http.post("https://example.org/post", {"q": "Borann"}) == [2]
    get, post = source.requests
    assert get.get_header("User-agent") == "EDRockMaster/test"
    assert get.get_header("Accept-encoding") == "gzip"
    assert post.get_method() == "POST"
    assert post.data == b'{"q": "Borann"}'
    assert post.get_header("Content-type") == "application/json"
    assert source.timeouts == [15.0, 15.0]


def test_a_form_is_posted_as_a_site_posts_it() -> None:
    # Spansh's route planner takes the form its site sends (ADR 0057)
    source, clock = FakeSource({"job": "J"}), Clock()
    assert client(source, clock).post_form(
        "https://example.org/route", {"system": "Sol", "max_hops": 3}
    ) == {"job": "J"}
    [post] = source.requests
    assert post.data == b"system=Sol&max_hops=3"
    assert post.get_header("Content-type") == "application/x-www-form-urlencoded"


def test_a_gzip_answer_is_read() -> None:
    body = FakeResponse(gzip.compress(b'{"ok": true}'), encoding="gzip")
    assert client(FakeSource(body), Clock()).get("https://example.org") == {"ok": True}


def test_requests_are_one_second_apart() -> None:
    source, clock = FakeSource([], [], []), Clock()
    http = client(source, clock)
    http.get("https://example.org")
    clock.now += 0.25
    http.get("https://example.org")
    clock.now += 5
    http.get("https://example.org")
    assert clock.slept == [pytest.approx(0.75)]


def test_too_many_requests_make_the_source_busy_for_its_retry_after() -> None:
    source, clock = FakeSource(http_error(429, "120"), []), Clock()
    http = client(source, clock)
    with pytest.raises(SourceError) as busy:
        http.get("https://example.org")
    assert busy.value.reason is Unavailable.BUSY
    clock.now += 60
    with pytest.raises(SourceError, match="busy for 60 s more"):
        http.get("https://example.org")
    assert len(source.requests) == 1  # not asked while busy
    clock.now += 61
    assert http.get("https://example.org") == []


def test_an_overloaded_source_waits_longer_each_time_up_to_ten_minutes() -> None:
    errors = [http_error(503) for _ in range(7)]
    source, clock = FakeSource(*errors, []), Clock()
    http = client(source, clock)
    waits = []
    for _ in range(7):
        start = clock.now
        with pytest.raises(SourceError):
            http.get("https://example.org")
        with pytest.raises(SourceError) as busy:
            http.get("https://example.org")
        assert busy.value.reason is Unavailable.BUSY
        waits.append(round(http._busy_until - start))
        clock.now = http._busy_until
    assert waits == [30, 60, 120, 240, 480, 600, 600]
    assert http.get("https://example.org") == []
    assert http._backoff is None  # a success starts again from 30 seconds


@pytest.mark.parametrize(
    "failure",
    [
        http_error(404),
        urllib.error.URLError("no network"),
        TimeoutError("timed out"),
        FakeResponse(b"<html>not json</html>"),
        FakeResponse(b"not gzip", encoding="gzip"),
    ],
)
def test_a_source_that_cannot_answer_is_down(failure: Any) -> None:
    with pytest.raises(SourceError) as down:
        client(FakeSource(failure), Clock()).get("https://example.org")
    assert down.value.reason is Unavailable.DOWN
