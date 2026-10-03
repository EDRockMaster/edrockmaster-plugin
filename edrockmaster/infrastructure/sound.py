"""Audible prospector alerts."""

from __future__ import annotations

import logging
import sys
import tkinter
from collections.abc import Callable

from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised

if sys.platform == "win32":  # pragma: no cover
    import winsound


class SoundNotifier:
    """Plays a short system sound for each alert. Never raises."""

    def __init__(self, play: Callable[[], None], logger: logging.Logger) -> None:
        self._play = play
        self._logger = logger

    def notify(self, alert: ProspectorAlertRaised) -> None:
        try:
            self._play()
        except Exception as error:
            self._logger.warning("Could not play the alert sound: %s", error)


def system_alert_sound(widget: tkinter.Misc) -> Callable[[], None]:  # pragma: no cover
    """Return a non-blocking way to play the system alert sound on this platform."""
    if sys.platform == "win32":
        return lambda: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    return widget.bell
