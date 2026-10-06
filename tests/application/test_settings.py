import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DEFAULT_SETTINGS, DisplayMode, DisplaySettings


def test_by_default_every_activity_is_shown_and_the_last_active_one_alone() -> None:
    assert DEFAULT_SETTINGS.display == DisplaySettings(
        activities=(Activity.MINING, Activity.COMBAT, Activity.TRADE), mode=DisplayMode.LAST_ACTIVE
    )


def test_activities_are_kept_in_their_display_order() -> None:
    display = DisplaySettings(activities=(Activity.COMBAT, Activity.MINING, Activity.COMBAT))
    assert display.activities == (Activity.MINING, Activity.COMBAT)


def test_at_least_one_activity_is_shown() -> None:
    with pytest.raises(ValueError, match="at least one activity"):
        DisplaySettings(activities=())
