"""The panel's presenter: shows the activity the player is busy with (ADR 0011).

Every notification reaches its activity's presenter, so a hidden activity stays
up to date; the panel shows the last activity whose session progressed.
Vouchers and community goals update the hunting presenter without switching.
"""

from __future__ import annotations

from collections.abc import Iterable

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Notification
from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntStarted,
    HuntUpdated,
    VouchersUpdated,
)
from edrockmaster.ui.hunting_presenter import HuntingPresenter
from edrockmaster.ui.mining_presenter import MiningPresenter
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    Translate,
    default_number_format,
    identity,
)

_HUNTING = (HuntStarted, HuntUpdated, HuntEnded, VouchersUpdated, CommunityGoalsChanged)
_HUNTING_PROGRESS = (HuntStarted, HuntUpdated, HuntEnded)


class ActivityPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._mining = MiningPresenter(translate, format_number)
        self._hunting = HuntingPresenter(translate, format_number)
        self.current = Activity.MINING

    def apply(self, notifications: Iterable[Notification]) -> PanelModel:
        for notification in notifications:
            if isinstance(notification, _HUNTING):
                self._hunting.apply([notification])
                if isinstance(notification, _HUNTING_PROGRESS):
                    self.current = Activity.BOUNTY_HUNTING
            else:
                self._mining.apply([notification])
                self.current = Activity.MINING
        return self.render()

    def render(self) -> PanelModel:
        if self.current is Activity.BOUNTY_HUNTING:
            return self._hunting.render()
        return self._mining.render()
