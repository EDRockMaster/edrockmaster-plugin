import pytest

from tests.scripts import load_script

release = load_script("github_release")


def test_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main(["v0.4.0", "abc1234"]) == 2
    assert "Usage" in capsys.readouterr().err


def test_a_token_is_needed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GH_RELEASE_TOKEN", raising=False)
    # Notes only, no file: what a production of the desktop application publishes (ADR 0024)
    assert release.main(["v0.4.0", "abc1234", "notes.md"]) == 2
    assert "GH_RELEASE_TOKEN" in capsys.readouterr().err
