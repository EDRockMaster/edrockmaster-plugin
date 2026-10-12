"""Audible mining alerts: the prospector's, and the limpets running out (ADR 0042).

How a sound is played depends on the platform: ``desktop/core.py`` gives the
function.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from edrockmaster.domain.mining.limpets import LimpetAlertRaised
from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised


class SoundNotifier:
    """Plays a short system sound for each alert. Never raises."""

    def __init__(self, play: Callable[[], None], logger: logging.Logger) -> None:
        self._play = play
        self._logger = logger

    def notify(self, alert: ProspectorAlertRaised | LimpetAlertRaised) -> None:
        try:
            self._play()
        except Exception as error:
            self._logger.warning("Could not play the alert sound: %s", error)
