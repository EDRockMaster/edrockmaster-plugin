"""The release plan: which channel a tag publishes to, and which tags are refused (ADR 0012)."""

import pytest

from tests.scripts import load_script

release_plan = load_script("release_plan")
Plan = release_plan.Plan
ReleaseError = release_plan.ReleaseError
plan = release_plan.plan


def test_a_candidate_tag_publishes_a_private_pre_release() -> None:
    assert plan("v0.3.0-rc.1", "0.3.0", ["v0.3.0-rc.1"]) == Plan(
        channel="candidate", version="0.3.0", candidate=1
    )


def test_a_final_tag_on_an_accepted_candidate_goes_to_production() -> None:
    assert plan("v0.3.0", "0.3.0", ["v0.3.0-rc.1", "v0.3.0-rc.2", "v0.3.0"]) == Plan(
        channel="production", version="0.3.0", candidate=None
    )


def test_a_final_tag_without_a_candidate_on_the_same_commit_is_refused() -> None:
    with pytest.raises(ReleaseError, match="candidate"):
        plan("v0.3.0", "0.3.0", ["v0.3.0"])


def test_a_candidate_of_another_version_does_not_count() -> None:
    with pytest.raises(ReleaseError, match="candidate"):
        plan("v0.3.0", "0.3.0", ["v0.2.9-rc.1", "v0.3.0"])


@pytest.mark.parametrize("tag", ["v0.3.0-rc.1", "v0.3.0"])
def test_the_tag_must_match_the_version_of_the_code(tag: str) -> None:
    with pytest.raises(ReleaseError, match="version"):
        plan(tag, "0.2.2", [tag, "v0.3.0-rc.1"])


@pytest.mark.parametrize(
    "tag", ["0.3.0", "v0.3", "v0.3.0-beta.1", "v0.3.0-rc", "v0.3.0-rc.0", "v0.3.0-rc.01"]
)
def test_malformed_tags_are_refused(tag: str) -> None:
    with pytest.raises(ReleaseError, match="tag"):
        plan(tag, "0.3.0", [tag])


def test_cli_writes_the_plan_for_the_workflow(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_plan.main(["v0.3.0-rc.2", "0.3.0", "v0.3.0-rc.2"]) == 0
    assert capsys.readouterr().out.splitlines() == ["channel=candidate", "prerelease=true"]


def test_cli_explains_a_refusal(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_plan.main(["v0.3.0", "0.3.0", "v0.3.0"]) == 1
    assert "candidate" in capsys.readouterr().err


def test_cli_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_plan.main([]) == 2
    assert "Usage" in capsys.readouterr().err
