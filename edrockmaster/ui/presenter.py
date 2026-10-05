"""The panel's presenter: shows the activity the player is busy with (ADR 0011).

Every notification reaches its activity's presenter, so a hidden activity stays
up to date; the panel shows the last activity whose session progressed
(ADR 0013): for combat, a session or a segment that starts or ends, a reward
or a crime. Vouchers and community goals update the combat presenter without
switching.
"""

from __future__ import annotations

from collections.abc import Iterable

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Notification
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatStarted,
    CombatUpdated,
    CommunityGoalsChanged,
    VouchersUpdated,
)
from edrockmaster.ui.combat_presenter import CombatPresenter
from edrockmaster.ui.mining_presenter import MiningPresenter
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    Translate,
    default_number_format,
    identity,
)

_COMBAT = (CombatStarted, CombatUpdated, CombatEnded, VouchersUpdated, CommunityGoalsChanged)
_COMBAT_PROGRESS = (CombatStarted, CombatUpdated, CombatEnded)


class ActivityPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._mining = MiningPresenter(translate, format_number)
        self._combat = CombatPresenter(translate, format_number)
        self.current = Activity.MINING

    def apply(self, notifications: Iterable[Notification]) -> PanelModel:
        for notification in notifications:
            if isinstance(notification, _COMBAT):
                self._combat.apply([notification])
                if isinstance(notification, _COMBAT_PROGRESS):
                    self.current = Activity.COMBAT
            else:
                self._mining.apply([notification])
                self.current = Activity.MINING
        return self.render()

    def render(self) -> PanelModel:
        if self.current is Activity.COMBAT:
            return self._combat.render()
        return self._mining.render()
