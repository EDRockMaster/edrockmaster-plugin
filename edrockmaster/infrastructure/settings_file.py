"""The desktop application's settings, in a JSON file of the data directory (ADR 0020).

It is the ``ConfigStore`` that ``KeyValueSettingsStore`` reads and checks the
settings from (``get_str``, ``get_bool``, ``set``). The file is read once, at start; each change
is written on the I/O thread, atomically (a new file, then renamed).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from edrockmaster.infrastructure.worker import Job

FILE_NAME = "settings.json"


class JsonFileConfig:
    def __init__(self, path: Path, submit: Callable[[Job], None], logger: logging.Logger) -> None:
        self.path = path
        self._submit = submit
        self._logger = logger
        self._values: dict[str, str | bool] = self._read()

    def get_str(self, key: str, /, *, default: str | None = None) -> str | None:
        value = self._values.get(key, default)
        return value if isinstance(value, str) or value is None else default

    def get_bool(self, key: str, /, *, default: bool | None = None) -> bool:
        value = self._values.get(key, default)
        return value if isinstance(value, bool) else bool(default)

    def set(self, key: str, value: str | bool, /) -> None:
        self._values[key] = value
        text = json.dumps(self._values, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self._submit(lambda: self._write(text))

    def _read(self) -> dict[str, str | bool]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as error:
            self._logger.warning("Settings %s unreadable, defaults used: %s", self.path, error)
            return {}
        if not isinstance(data, dict):
            self._logger.warning("Settings %s unreadable, defaults used: not an object", self.path)
            return {}
        return {key: value for key, value in data.items() if isinstance(value, str | bool)}

    def _write(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_name(self.path.name + ".partial")
        partial.write_text(text, encoding="utf-8")
        partial.replace(self.path)
