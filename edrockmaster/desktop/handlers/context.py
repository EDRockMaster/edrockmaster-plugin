"""The narrow part of the desktop core the handlers reach (ADR 0041)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.ports import Clock

type Job = Callable[[], None]


@dataclass(frozen=True)
class CoreContext:
    """What a handler may do with the core; a test gives one that runs jobs at once.

    ``on_core`` and ``on_io`` queue a job for the core thread or the I/O thread;
    ``companion`` is the core's, once started; ``apply`` hands notifications to the
    presenter and pushes the view; ``refresh`` pushes the view again; ``tl`` translates
    in the language in use, and ``language`` names it."""

    on_core: Callable[[Job], None]
    on_io: Callable[[Job], None]
    companion: Callable[[], Companion]
    apply: Callable[[Sequence[Notification]], None]
    refresh: Callable[[], None]
    tl: Callable[[str], str]
    language: Callable[[], str]
    clock: Clock
    logger: logging.Logger
