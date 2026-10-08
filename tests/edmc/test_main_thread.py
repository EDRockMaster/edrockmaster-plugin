"""Callbacks from the I/O thread run on Tk's main thread (needs a display)."""

import logging
import threading
import time
import tkinter as tk

import pytest

from edrockmaster.edmc.main_thread import MainThreadDispatcher

logger = logging.getLogger("test.main_thread")


def run_events_until(root: tk.Tk, done: threading.Event | list[str]) -> None:
    deadline = time.monotonic() + 2
    while not done and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def test_callbacks_wait_for_the_widget_then_run_in_order(root: tk.Tk) -> None:
    dispatcher = MainThreadDispatcher(logger)
    seen: list[int] = []
    dispatcher.dispatch(lambda: seen.append(1))
    dispatcher.dispatch(lambda: seen.append(2))
    assert seen == []
    dispatcher.attach(root)
    assert seen == [1, 2]


def test_a_callback_from_another_thread_runs_on_the_main_thread(root: tk.Tk) -> None:
    dispatcher = MainThreadDispatcher(logger, poll_ms=10)
    dispatcher.attach(root)
    threads: list[str] = []
    worker = threading.Thread(
        target=dispatcher.dispatch,
        args=(lambda: threads.append(threading.current_thread().name),),
    )
    worker.start()
    worker.join()
    assert threads == []
    run_events_until(root, threads)
    assert threads == [threading.current_thread().name]


def test_a_failing_callback_is_logged_and_the_next_still_runs(
    root: tk.Tk, caplog: pytest.LogCaptureFixture
) -> None:
    dispatcher = MainThreadDispatcher(logger)
    seen: list[str] = []

    def fail() -> None:
        raise ValueError("broken result")

    dispatcher.dispatch(fail)
    dispatcher.dispatch(lambda: seen.append("next"))
    with caplog.at_level(logging.ERROR):
        dispatcher.attach(root)
    assert seen == ["next"]
    assert "broken result" in caplog.text


def test_polling_stops_when_the_widget_is_gone(root: tk.Tk) -> None:
    dispatcher = MainThreadDispatcher(logger, poll_ms=10)
    frame = tk.Frame(root)
    dispatcher.attach(frame)
    frame.destroy()
    seen: list[str] = []
    dispatcher.dispatch(lambda: seen.append("late"))
    run_events_until(root, seen)
    assert seen == []
