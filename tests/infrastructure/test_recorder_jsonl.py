import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from edrockmaster.domain.journal import Entry
from edrockmaster.infrastructure.recorder_jsonl import JsonlJournalRecorder

STARTED = datetime(2026, 10, 3, 14, 5, 9, tzinfo=UTC)


class DeferredJobs:
    """Stands for the I/O thread: jobs run only when asked."""

    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []

    def submit(self, job: Callable[[], None]) -> None:
        self.jobs.append(job)

    def run_all(self) -> None:
        jobs, self.jobs = self.jobs, []
        for job in jobs:
            job()


def make_recorder(tmp_path: Path, jobs: DeferredJobs) -> JsonlJournalRecorder:
    return JsonlJournalRecorder(tmp_path / "recordings", jobs.submit, STARTED)


def read_lines(path: Path) -> list[object]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_entries_are_appended_as_json_lines_with_the_beta_flag(tmp_path: Path) -> None:
    jobs = DeferredJobs()
    recorder = make_recorder(tmp_path, jobs)
    first: Entry = {"timestamp": "2026-10-03T14:05:10Z", "event": "Music"}
    second: Entry = {"timestamp": "2026-10-03T14:05:11Z", "event": "MiningRefined", "Type": "é"}
    recorder.record(first, is_beta=False)
    recorder.record(second, is_beta=True)
    jobs.run_all()
    assert read_lines(recorder.path) == [
        {"is_beta": False, "entry": first},
        {"is_beta": True, "entry": second},
    ]


def test_one_file_per_run_named_after_its_start(tmp_path: Path) -> None:
    recorder = make_recorder(tmp_path, DeferredJobs())
    assert recorder.path == tmp_path / "recordings" / "journal-20261003T140509Z.jsonl"


def test_writing_happens_on_the_io_thread_only(tmp_path: Path) -> None:
    jobs = DeferredJobs()
    recorder = make_recorder(tmp_path, jobs)
    recorder.record({"event": "Music"}, is_beta=False)
    assert not recorder.path.exists()
    jobs.run_all()
    assert recorder.path.exists()


def test_entry_is_captured_when_recorded_not_when_written(tmp_path: Path) -> None:
    jobs = DeferredJobs()
    recorder = make_recorder(tmp_path, jobs)
    entry = {"event": "Cargo", "Count": 1}
    recorder.record(entry, is_beta=False)
    entry["Count"] = 2  # EDMC hands the same dict to every plugin
    jobs.run_all()
    assert read_lines(recorder.path) == [
        {"is_beta": False, "entry": {"event": "Cargo", "Count": 1}}
    ]


def test_values_json_cannot_encode_are_written_as_text(tmp_path: Path) -> None:
    jobs = DeferredJobs()
    recorder = make_recorder(tmp_path, jobs)
    recorder.record({"event": "Odd", "When": STARTED}, is_beta=False)
    jobs.run_all()
    assert read_lines(recorder.path) == [
        {"is_beta": False, "entry": {"event": "Odd", "When": "2026-10-03 14:05:09+00:00"}}
    ]
