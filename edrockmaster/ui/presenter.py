"""The panel's presenter: shows the activities the player is busy with (ADR 0011, ADR 0013).

Every notification reaches its activity's presenter, so a hidden activity stays
up to date. The player chooses the activities shown and the mode:

- **last active**: one block, the last shown activity whose session progressed:
  for combat, a session or a segment that starts or ends, a reward or a crime.
  Vouchers and community goals update the combat presenter without switching.
  For trade, a session that starts or ends, a purchase, a sale or a loss
  (ADR 0014);
- **stacked**: one block per activity shown, in display order.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Notification
from edrockmaster.application.settings import DisplayMode, DisplaySettings
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatStarted,
    CombatUpdated,
    CommunityGoalsChanged,
    VouchersUpdated,
)
from edrockmaster.domain.trade.session import TradeEnded, TradeStarted, TradeUpdated
from edrockmaster.ui.combat_presenter import CombatPresenter
from edrockmaster.ui.mining_presenter import MiningPresenter
from edrockmaster.ui.panel_model import (
    ActivityBlock,
    NumberFormat,
    PanelModel,
    Translate,
    default_number_format,
    identity,
)
from edrockmaster.ui.trade_presenter import TradePresenter

_COMBAT = (CombatStarted, CombatUpdated, CombatEnded, VouchersUpdated, CommunityGoalsChanged)
_COMBAT_PROGRESS = (CombatStarted, CombatUpdated, CombatEnded)
_TRADE = (TradeStarted, TradeUpdated, TradeEnded)


class ActivityPresenter:
    def __init__(
        self,
        translate: Translate = identity,
        format_number: NumberFormat = default_number_format,
        display: DisplaySettings | None = None,
    ) -> None:
        self._mining = MiningPresenter(translate, format_number)
        self._combat = CombatPresenter(translate, format_number)
        self._trade = TradePresenter(translate, format_number)
        self._display = display or DisplaySettings()
        self.current = self._display.activities[0]
        """The activity shown in the last active mode."""

    def configure(self, display: DisplaySettings) -> None:
        self._display = display
        if self.current not in display.activities:
            self.current = display.activities[0]

    def apply(self, notifications: Iterable[Notification]) -> PanelModel:
        for notification in notifications:
            if isinstance(notification, _COMBAT):
                self._combat.apply([notification])
                if isinstance(notification, _COMBAT_PROGRESS):
                    self._progressed(Activity.COMBAT)
            elif isinstance(notification, _TRADE):
                self._trade.apply([notification])
                self._progressed(Activity.TRADE)
            else:
                self._mining.apply([notification])
                self._progressed(Activity.MINING)
        return self.render()

    def render(self) -> PanelModel:
        """The model of the activity shown in the last active mode."""
        return self._model(self.current)

    def blocks(self) -> tuple[ActivityBlock, ...]:
        """What the panel shows, in the player's display mode."""
        if self._display.mode is DisplayMode.STACKED:
            shown = self._display.activities
        else:
            shown = (self.current,)
        return tuple(ActivityBlock(activity, self._model(activity)) for activity in shown)

    def _progressed(self, activity: Activity) -> None:
        if activity in self._display.activities:
            self.current = activity

    def _model(self, activity: Activity) -> PanelModel:
        match activity:
            case Activity.MINING:
                return self._mining.render()
            case Activity.COMBAT:
                return self._combat.render()
            case Activity.TRADE:
                return self._trade.render()
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(activity)
