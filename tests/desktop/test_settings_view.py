"""The settings form of the desktop application (ADR 0020)."""

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DEFAULT_SETTINGS, DisplayMode, SourceSettings
from edrockmaster.application.updates import UpdateChannel
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    SettingsError,
    UpdateOffer,
    settings_from_request,
    settings_view,
)
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from tests.desktop.schemas import LIVE_VIEW_SCHEMA as SCHEMA
from tests.fakes import FakeConfig

JOURNAL = Path("/games/journal").resolve()
RECORDINGS = Path("/data/recordings").resolve()
LOGS = Path("/data/logs").resolve()


INSTALLED = UpdateOffer(installed=True, default=UpdateChannel.STABLE)


def view(
    language: str = "auto",
    folder: str | None = None,
    preferences: DesktopPreferences | None = None,
    offer: UpdateOffer = INSTALLED,
) -> dict[str, Any]:
    return settings_view(
        DEFAULT_SETTINGS,
        preferences or DesktopPreferences(language, folder),
        JOURNAL,
        lambda text: text,
        {"recordings": RECORDINGS, "logs": LOGS},
        updates=offer,
    )


def from_request(
    request: dict[str, Any], offer: UpdateOffer = INSTALLED
) -> tuple[Any, DesktopPreferences]:
    return settings_from_request(request, DEFAULT_SETTINGS, offer.default)


def test_the_form_shows_the_settings() -> None:
    shown = view()
    painite = next(row for row in shown["alerts"]["thresholds"] if row["commodity"] == "painite")
    assert painite["name"] == "Painite"
    assert shown["alerts"]["minimumContent"] in ("low", "medium", "high")
    assert shown["alerts"]["limpets"] == 5
    assert shown["activities"] == [activity.value for activity in Activity]
    assert shown["language"] == "auto"
    assert shown["journalFolder"] is None
    assert shown["journalFolderInUse"] == str(JOURNAL)
    # Where the journal recordings and the application's logs go, for a bug report
    assert shown["recordingsFolder"] == str(RECORDINGS)
    assert shown["logsFolder"] == str(LOGS)


def test_the_form_back_into_settings() -> None:
    request = view()
    for row in request["alerts"]["thresholds"]:
        row["threshold"] = 35 if row["commodity"] == "painite" else None
    request["alerts"].update(minimumContent="high", minimumRemaining=50, cores=False, limpets=None)
    request.update(sound=False, recordJournal=True, activities=["trade", "mining"], language="fr")
    request["journalFolder"] = f"  {JOURNAL}  "
    settings, preferences = from_request(request)
    assert dict(settings.alerts.thresholds) == {Commodity.from_symbol("painite"): 35.0}
    assert settings.alerts.minimum_content is ContentLevel.HIGH
    assert settings.alerts.minimum_remaining == 50.0
    assert not settings.alerts.alert_on_cores
    assert settings.alerts.limpet_alert is None
    assert (settings.sound_enabled, settings.record_journal) == (False, True)
    assert settings.display.activities == (Activity.MINING, Activity.TRADE)
    assert settings.display.mode is DisplayMode.LAST_ACTIVE  # the plugin's, kept
    assert preferences == DesktopPreferences("fr", str(JOURNAL))


def test_the_community_sources_are_switched_in_the_form() -> None:
    request = view()
    assert request["sources"] == {"spansh": True, "ardent": True}
    request["sources"] = {"spansh": False, "ardent": True}
    assert from_request(request)[0].sources == SourceSettings(spansh=False)


def test_an_empty_folder_means_the_usual_one() -> None:
    request = view()
    request["journalFolder"] = "  "
    assert from_request(request)[1].journal_folder is None


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
        (("alerts", "limpets"), -1, "limpets"),
        (("alerts", "limpets"), 2.5, "limpets"),
        (("alerts", "limpets"), True, "limpets"),
        (("alerts", "limpets"), 1000, "limpets"),
        (("sound",), 1, "sound"),
        (("sources",), None, "sources"),
        (("sources", "ardent"), "yes", "ardent"),
        (("activities",), [], "activities"),
        (("activities",), "mining", "activities"),
        (("activities",), ["piracy"], "activities"),
        (("language",), "de", "language"),
        (("journalFolder",), 3, "journalFolder"),
        (("journalFolder",), "relative/folder", "journalFolder"),
        (("updates",), None, "updates"),
        (("updates", "check"), "yes", "check"),
        (("updates", "channel"), "nightly", "channel"),
    ],
)
def test_invalid_fields_are_refused(path: tuple[str, ...], value: object, field: str) -> None:
    with pytest.raises(SettingsError) as refused:
        from_request(changed(path, value))
    assert refused.value.field == field


def test_the_desktop_preferences_are_stored_next_to_the_plugin_s() -> None:
    config = FakeConfig()
    store = DesktopPreferencesStore(config)
    assert store.load() == DesktopPreferences()
    store.save(DesktopPreferences("fr", "D:/Journal"))
    assert store.load() == DesktopPreferences("fr", "D:/Journal")
    config.values["edrockmaster.desktop.language"] = "klingon"
    assert store.load().language == "auto"


# --- updates (ADR 0053) ----------------------------------------------------------------------


def test_the_updates_follow_the_build_s_channel_until_another_is_chosen() -> None:
    assert view()["updates"] == {"installed": True, "check": True, "channel": "stable"}
    candidate = UpdateOffer(installed=True, default=UpdateChannel.BETA)
    assert view(offer=candidate)["updates"]["channel"] == "beta"
    chosen = DesktopPreferences(update_channel=UpdateChannel.BETA)
    assert view(preferences=chosen)["updates"]["channel"] == "beta"


def test_an_application_not_installed_says_so() -> None:
    clone = UpdateOffer(installed=False, default=None)
    assert view(offer=clone)["updates"] == {"installed": False, "check": True, "channel": "stable"}


def test_the_form_back_into_update_preferences() -> None:
    request = view()
    request["updates"] = {"installed": True, "check": False, "channel": "beta"}
    preferences = from_request(request)[1]
    assert (preferences.check_updates, preferences.update_channel) == (False, UpdateChannel.BETA)


def test_the_build_s_channel_is_not_kept_as_a_choice() -> None:
    # A candidate updated to the production that ends its acceptance then follows stable
    candidate = UpdateOffer(installed=True, default=UpdateChannel.BETA)
    assert from_request(view(offer=candidate), candidate)[1].update_channel is None


def test_the_update_preferences_are_stored() -> None:
    config = FakeConfig()
    store = DesktopPreferencesStore(config)
    store.save(DesktopPreferences(check_updates=False, update_channel=UpdateChannel.BETA))
    assert store.load() == DesktopPreferences(
        check_updates=False, update_channel=UpdateChannel.BETA
    )
    config.values["edrockmaster.desktop.update_channel"] = "nightly"
    assert store.load().update_channel is None


def test_the_form_follows_its_schema() -> None:
    schema = json.loads((SCHEMA.parent / "settings.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(view("fr", str(JOURNAL)))
