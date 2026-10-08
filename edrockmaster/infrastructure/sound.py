"""Audible prospector alerts.

How a sound is played depends on the host: EDMC's Tk window (``edmc/host.py``)
or the desktop application (``desktop/core.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised


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
