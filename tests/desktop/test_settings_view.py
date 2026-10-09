"""The settings form of the desktop application (ADR 0020)."""

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DEFAULT_SETTINGS, DisplayMode
from edrockmaster.desktop.live_view import SCHEMA
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    SettingsError,
    settings_from_request,
    settings_view,
)
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from tests.fakes import FakeConfig

JOURNAL = Path("/games/journal").resolve()


def view(language: str = "auto", folder: str | None = None) -> dict[str, Any]:
    return settings_view(
        DEFAULT_SETTINGS, DesktopPreferences(language, folder), JOURNAL, lambda text: text
    )


def test_the_form_shows_the_settings() -> None:
    shown = view()
    painite = next(row for row in shown["alerts"]["thresholds"] if row["commodity"] == "painite")
    assert painite["name"] == "Painite"
    assert shown["alerts"]["minimumContent"] in ("low", "medium", "high")
    assert shown["activities"] == [activity.value for activity in Activity]
    assert shown["language"] == "auto"
    assert shown["journalFolder"] is None
    assert shown["journalFolderInUse"] == str(JOURNAL)


def test_the_form_back_into_settings() -> None:
    request = view()
    for row in request["alerts"]["thresholds"]:
        row["threshold"] = 35 if row["commodity"] == "painite" else None
    request["alerts"].update(minimumContent="high", minimumRemaining=50, cores=False)
    request.update(sound=False, recordJournal=True, activities=["trade", "mining"], language="fr")
    request["journalFolder"] = f"  {JOURNAL}  "
    settings, preferences = settings_from_request(request, DEFAULT_SETTINGS)
    assert dict(settings.alerts.thresholds) == {Commodity.from_symbol("painite"): 35.0}
    assert settings.alerts.minimum_content is ContentLevel.HIGH
    assert settings.alerts.minimum_remaining == 50.0
    assert not settings.alerts.alert_on_cores
    assert (settings.sound_enabled, settings.record_journal) == (False, True)
    assert settings.display.activities == (Activity.MINING, Activity.TRADE)
    assert settings.display.mode is DisplayMode.LAST_ACTIVE  # the plugin's, kept
    assert preferences == DesktopPreferences("fr", str(JOURNAL))


def test_an_empty_folder_means_the_usual_one() -> None:
    request = view()
    request["journalFolder"] = "  "
    assert settings_from_request(request, DEFAULT_SETTINGS)[1].journal_folder is None


def changed(path: tuple[str, ...], value: object) -> dict[str, Any]:
    request = copy.deepcopy(view())
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return request


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (("alerts",), None, "alerts"),
        (("alerts", "thresholds"), None, "thresholds"),
        (("alerts", "thresholds"), [{"commodity": "gold", "threshold": 101}], "threshold.gold"),
        (("alerts", "thresholds"), [{"commodity": "gold", "threshold": True}], "threshold.gold"),
        (("alerts", "thresholds"), [{"commodity": "unobtainium", "threshold": 1}], "thresholds"),
        (("alerts", "minimumContent"), "unknown", "minimumContent"),
        (("alerts", "minimumRemaining"), -1, "minimumRemaining"),
        (("alerts", "cores"), "yes", "cores"),
        (("sound",), 1, "sound"),
        (("activities",), [], "activities"),
        (("activities",), "mining", "activities"),
        (("activities",), ["piracy"], "activities"),
        (("language",), "de", "language"),
        (("journalFolder",), 3, "journalFolder"),
        (("journalFolder",), "relative/folder", "journalFolder"),
    ],
)
def test_invalid_fields_are_refused(path: tuple[str, ...], value: object, field: str) -> None:
    with pytest.raises(SettingsError) as refused:
        settings_from_request(changed(path, value), DEFAULT_SETTINGS)
    assert refused.value.field == field


def test_the_desktop_preferences_are_stored_next_to_the_plugin_s() -> None:
    config = FakeConfig()
    store = DesktopPreferencesStore(config)
    assert store.load() == DesktopPreferences()
    store.save(DesktopPreferences("fr", "D:/Journal"))
    assert store.load() == DesktopPreferences("fr", "D:/Journal")
    config.values["edrockmaster.desktop.language"] = "klingon"
    assert store.load().language == "auto"


def test_the_form_follows_its_schema() -> None:
    schema = json.loads((SCHEMA.parent / "settings.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(view("fr", str(JOURNAL)))
