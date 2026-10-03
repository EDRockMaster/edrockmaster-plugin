"""Translation of displayed strings, through EDMC's ``l10n``.

Source strings are English; translations live in ``L10n/<lang>.strings`` at the
plugin's root. Outside EDMC (tests, tooling), strings are returned unchanged.
"""

from __future__ import annotations

try:  # pragma: no cover - only available inside EDMC
    from l10n import translations as _translations  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - outside EDMC
    _translations = None


def tl(text: str) -> str:
    """Return ``text`` in EDMC's current language, English if no translation exists."""
    if _translations is None:
        return text
    # EDMC finds the plugin's L10n folder from any file path inside the plugin
    translated: str = _translations.tl(text, context=__file__)
    return translated
