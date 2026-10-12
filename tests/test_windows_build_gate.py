"""The Gitea check that waits for the Windows build on the GitHub mirror (ADR 0034)."""

import urllib.error
from email.message import Message
from pathlib import Path

import pytest

from tests.scripts import load_script

gate = load_script("windows_build_gate")
Run = gate.Run
WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "windows.yml"
PATTERNS = ["**.md", "docs/**", ".gitea/**"]


def run(sha: str, conclusion: str | None = "success", branch: str = "main", at: int = 0) -> object:
    status = "completed" if conclusion else "in_progress"
    return Run(sha, status, conclusion, f"https://github.com/runs/{sha}{at}", branch, at)


def changes(files: dict[tuple[str, str], list[str]]):  # type: ignore[no-untyped-def]
    return lambda a, b: files[(a, b)]


def test_the_patterns_are_read_from_the_windows_workflow() -> None:
    assert gate.ignored_patterns(WORKFLOW.read_text(encoding="utf-8")) == PATTERNS


@pytest.mark.parametrize(
    ("path", "ignored"),
    [
        ("README.md", True),
        ("docs/design.fr.md", True),
        ("docs/images/shot.png", True),
        (".gitea/workflows/ci.yml", True),
        ("CHANGELOG.md", True),
        ("edrockmaster/desktop/core.py", False),
        ("packaging/windows/EDRockMaster.spec", False),
        ("web/src/App.svelte", False),
        ("mdfile", False),
    ],
)
def test_what_the_windows_build_ignores(path: str, ignored: bool) -> None:
    assert gate.ignorable(path, PATTERNS) is ignored


def test_the_commit_s_own_build_is_waited_for_then_taken() -> None:
    running = gate.decide(
        "c", ["c", "b"], {"c": [run("c", None)]}, changed=changes({}), base=None, patterns=PATTERNS
    )
    assert running == gate.Wait(run("c", None))
    done = gate.decide(
        "c", ["c"], {"c": [run("c", "failure")]}, changed=changes({}), base=None, patterns=PATTERNS
    )
    assert done == gate.Result(run("c", "failure"))


def test_after_documentation_only_the_last_build_counts() -> None:
    files = changes({("b", "c"): ["docs/design.md", "README.fr.md"]})
    decision = gate.decide(
        "c", ["c", "b"], {"b": [run("b")]}, changed=files, base=None, patterns=PATTERNS
    )
    assert decision == gate.Result(run("b"))


def test_after_code_the_commit_s_own_build_must_come() -> None:
    files = changes({("b", "c"): ["edrockmaster/desktop/core.py"]})
    assert gate.decide(
        "c", ["c", "b"], {"b": [run("b")]}, changed=files, base=None, patterns=PATTERNS
    ) == gate.Wait(None)


def test_no_build_needed_when_the_branch_changed_documentation_only() -> None:
    files = changes({("base", "c"): ["docs/store-listing.md"]})
    decision = gate.decide("c", ["c", "b"], {}, changed=files, base="base", patterns=PATTERNS)
    assert decision == gate.NO_BUILD_NEEDED


def test_without_any_build_nor_base_the_check_waits() -> None:
    assert gate.decide(
        "c", ["c"], {}, changed=changes({}), base=None, patterns=PATTERNS
    ) == gate.Wait(None)


def test_a_tag_takes_its_own_run_over_the_branch_s() -> None:
    runs = {"c": [run("c", "success", "main", at=1), run("c", "failure", "v1.0.0-rc.1", at=2)]}
    decision = gate.decide(
        "c", ["c"], runs, changed=changes({}), base=None, patterns=PATTERNS, prefer="v1.0.0-rc.1"
    )
    assert decision == gate.Result(run("c", "failure", "v1.0.0-rc.1", at=2))
    # Otherwise, the latest run of the commit: a rerun's result
    latest = gate.decide("c", ["c"], runs, changed=changes({}), base=None, patterns=PATTERNS)
    assert latest == gate.Result(run("c", "failure", "v1.0.0-rc.1", at=2))


def test_runs_are_grouped_by_commit_from_the_api() -> None:
    payload = {
        "workflow_runs": [
            {
                "head_sha": "c",
                "status": "completed",
                "conclusion": "success",
                "html_url": "u",
                "head_branch": "main",
                "created_at": "2026-10-11T12:30:01Z",
            }
        ]
    }
    [only] = gate.runs_by_commit(payload)["c"]
    assert (only.conclusion, only.url, only.branch) == ("success", "u", "main")


def test_github_not_answering_is_asked_again() -> None:
    def bad_gateway(_token: str | None) -> dict[str, list[object]]:
        raise urllib.error.HTTPError("https://api.github.com", 502, "Bad Gateway", Message(), None)

    def timeout(_token: str | None) -> dict[str, list[object]]:
        raise TimeoutError("timed out")

    assert gate.latest_runs(None, bad_gateway) is None
    assert gate.latest_runs(None, timeout) is None
    assert gate.latest_runs(None, lambda _token: {}) == {}
