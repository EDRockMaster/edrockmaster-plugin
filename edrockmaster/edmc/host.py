"""Services EDMC offers to plugins, with plain fallbacks outside EDMC (tests, tooling).

Only the imports EDMC documents as plugin API are used: ``theme``, ``plug.show_error``
and ``l10n.Locale``.
"""

from __future__ import annotations

import logging
import tkinter as tk

from edrockmaster.ui.panel_model import default_number_format

try:  # pragma: no cover - only available inside EDMC
    import plug  # type: ignore[import-not-found]
    from l10n import Locale  # type: ignore[import-not-found]
    from theme import theme  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - outside EDMC
    plug = Locale = theme = None

_logger = logging.getLogger(__name__)


def format_number(number: float, decimals: int) -> str:
    """Number in the system's locale, as EDMC shows its own."""
    if Locale is None:
        return default_number_format(number, decimals)
    formatted: str = Locale.string_from_number(number, decimals)
    return formatted


def parse_number(text: str) -> float | None:
    """Number typed by the player in the system's locale, ``None`` if invalid."""
    if Locale is None:
        try:
            return float(text)
        except ValueError:
            return None
    value: int | float | None = Locale.number_from_string(text)
    return None if value is None else float(value)


def theme_update(widget: tk.Widget) -> None:
    """Theme a widget created after ``plugin_app()``."""
    if theme is not None:  # pragma: no cover - only inside EDMC
        theme.update(widget)


def show_error(message: str) -> None:
    """Show a message in EDMC's status bar."""
    if plug is None:
        _logger.warning("%s", message)
    else:  # pragma: no cover - only inside EDMC
        plug.show_error(message)
