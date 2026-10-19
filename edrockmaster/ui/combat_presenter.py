"""Combat presenter: combat notifications in, panel texts out (ADR 0013)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import assert_never

from edrockmaster.domain.combat.journal import VoucherKind
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatNotification,
    CombatStarted,
    CombatStats,
    CombatUpdated,
    SegmentStats,
    SiteAverage,
    Tally,
)
from edrockmaster.domain.combat.sites import SiteType
from edrockmaster.domain.combat.vouchers import HeldVoucher, VouchersUpdated
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    StatLine,
    Translate,
    default_number_format,
    format_credits,
    format_day,
    format_duration,
    identity,
)

# English source strings, translated at render time
_END_REASONS = {
    CombatEndReason.GAME_CLOSED: "game closed",
    CombatEndReason.DIED: "ship destroyed",
    CombatEndReason.MANUAL: "reset",
}
SITE_NAMES = {
    SiteType.CONFLICT_ZONE_LOW: "Conflict zone, low",
    SiteType.CONFLICT_ZONE_MEDIUM: "Conflict zone, medium",
    SiteType.CONFLICT_ZONE_HIGH: "Conflict zone, high",
    SiteType.RES_LOW: "RES, low",
    SiteType.RES: "RES",
    SiteType.RES_HIGH: "RES, high",
    SiteType.RES_HAZARDOUS: "RES, hazardous",
    SiteType.NAV_BEACON: "Nav beacon",
    SiteType.CONFLICT_ZONE_UNKNOWN: "Conflict zone, unknown intensity",
    SiteType.GROUND_CONFLICT_ZONE: "Ground conflict zone",
    SiteType.UNKNOWN: "Unknown site",
}


# The crimes of ``CommitCrime`` (``CrimeType``), as the journal names them; any other is shown
# from its symbol, in English
CRIME_NAMES = {
    "assault": "Assault",
    "murder": "Murder",
    "piracy": "Piracy",
    "interdiction": "Illegal interdiction",
    "illegalCargo": "Illegal cargo",
    "disobeyPolice": "Disobeying the police",
    "fireInNoFireZone": "Firing in a no-fire zone",
    "fireInStation": "Firing in a station",
    "dumpingDangerous": "Dumping dangerous cargo",
    "dumpingNearStation": "Dumping near a station",
    "dockingMinorBlockingAirlock": "Blocking an airlock",
    "dockingMajorBlockingAirlock": "Blocking an airlock, major",
    "dockingMinorBlockingLandingPad": "Blocking a landing pad",
    "dockingMajorBlockingLandingPad": "Blocking a landing pad, major",
    "dockingMinorTrespass": "Trespassing at a station",
    "dockingMajorTrespass": "Trespassing at a station, major",
    "collidedAtSpeedInNoFireZone": "Collision at speed in a no-fire zone",
    "collidedAtSpeedInNoFireZone_hulldamage": "Collision at speed in a no-fire zone, hull damaged",
    "recklessWeaponsDischarge": "Reckless weapons discharge",
    "passengerWanted": "Carrying a wanted passenger",
}
_ON_FOOT_PREFIX = "onFoot_"
_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
FACTIONS_SHOWN = 3
"""Victim factions, or unredeemed vouchers, with a line of their own; the others add up in one."""
_UNREDEEMED = {
    VoucherKind.BOUNTY: "Unredeemed bounties, {faction}",
    VoucherKind.COMBAT_BOND: "Unredeemed combat bonds, {faction}",
}


class CombatPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ended: CombatEndReason | None = None
        self._stats: CombatStats | None = None
        self._vouchers: VouchersUpdated | None = None

    def apply(self, notifications: Iterable[CombatNotification | VouchersUpdated]) -> PanelModel:
        for notification in notifications:
            self._apply(notification)
        return self.render()

    def render(self) -> PanelModel:
        lines = list(self._session_lines(self._stats)) if self._stats else []
        if self._vouchers is not None:
            lines += self._voucher_lines(self._vouchers)
        return PanelModel(
            status=self._status(), lines=tuple(lines), alert=None, can_reset=self._running
        )

    def forget_ended(self) -> None:
        """The session ended belongs to a past game: no longer shown (a running one stays)."""
        if not self._running:
            self._ended, self._stats = None, None

    def _apply(self, notification: CombatNotification | VouchersUpdated) -> None:
        match notification:
            case CombatStarted():
                self._running, self._ended, self._stats = True, None, None
            case CombatUpdated(stats=stats):
                self._stats = stats
            case CombatEnded(reason=reason, stats=stats):
                self._running, self._ended, self._stats = False, reason, stats
            case VouchersUpdated():
                self._vouchers = notification
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(notification)

    def _status(self) -> str:
        tl = self._tl
        if self._running:
            current = self._stats.current if self._stats else None
            return self._site_status(current) if current else tl("Combat")
        if self._ended is not None:
            return tl("Combat session ended: {reason}").format(reason=tl(_END_REASONS[self._ended]))
        return tl("No combat session")

    def _site_status(self, segment: SegmentStats) -> str:
        site = self._tl(SITE_NAMES[segment.site])
        if segment.settlement is None:
            return site
        return self._tl("{site}: {settlement}").format(site=site, settlement=segment.settlement)

    def _session_lines(self, stats: CombatStats) -> Iterable[StatLine]:
        tl, number = self._tl, self._number
        if stats.segments:
            yield StatLine(tl("Active time"), format_duration(stats.active_duration, tl))
        kills = number(stats.kills, 0)
        if stats.shared_kills:
            kills = tl("{kills} ({shared} shared)").format(
                kills=kills, shared=number(stats.shared_kills, 0)
            )
        yield StatLine(tl("Kills"), kills)
        if stats.bounty_credits or not stats.bond_credits:
            # In a conflict zone, only combat bonds are earned: no empty bounty line
            yield StatLine(tl("Bounties earned"), self._credits(stats.bounty_credits))
        if stats.bond_credits:
            yield StatLine(tl("Combat bonds earned"), self._credits(stats.bond_credits))
        if stats.current is not None:
            yield StatLine(tl("This site"), self._segment_text(stats.current))
        yield from (self._average_line(average) for average in stats.by_site())
        if stats.miscellaneous != Tally():
            yield StatLine(tl("Miscellaneous"), self._tally_text(stats.miscellaneous))
        if stats.crimes.fines:
            yield StatLine(tl("Fines"), self._credits(stats.crimes.fines))
        if stats.crimes.bounties:
            yield StatLine(tl("Bounty on you"), self._credits(stats.crimes.bounties))
        if stats.crimes.by_kind:
            yield StatLine(tl("Crimes"), self._crimes_text(stats.crimes.by_kind))
        yield from self._faction_lines(stats.by_victim_faction)

    def _voucher_lines(self, updated: VouchersUpdated) -> Iterable[StatLine]:
        """The vouchers held (ADR 0052): the total if several, then the largest first; none
        said once the past journals are read."""
        tl = self._tl
        held = sorted(updated.vouchers.held, key=lambda voucher: -voucher.amount)
        if not held and updated.past.complete:
            yield StatLine(tl("Unredeemed"), tl("none"))
        if len(held) > 1:
            yield StatLine(tl("Unredeemed"), self._credits(updated.vouchers.total))
        yield from (self._voucher_line(voucher) for voucher in held[:FACTIONS_SHOWN])
        others = held[FACTIONS_SHOWN:]
        if others:
            label = tl("Unredeemed from {count} other factions").format(
                count=self._number(len(others), 0)
            )
            yield StatLine(label, self._credits(sum(voucher.amount for voucher in others)))
        if not updated.past.complete:
            reading = tl("reading: {read} / {total}").format(
                read=self._number(updated.past.read, 0), total=self._number(updated.past.total, 0)
            )
            yield StatLine(tl("Past journals"), reading)

    def _voucher_line(self, voucher: HeldVoucher) -> StatLine:
        tl = self._tl
        value = tl("{credits}, since {day}").format(
            credits=self._credits(voucher.amount), day=format_day(voucher.since, tl)
        )
        return StatLine(tl(_UNREDEEMED[voucher.kind]).format(faction=voucher.faction), value)

    def _crimes_text(self, by_kind: Mapping[str, int]) -> str:
        """Most frequent first; a crime of equal count in the order it came."""
        ranked = sorted(by_kind.items(), key=lambda item: -item[1])
        return ", ".join(
            self._tl("{crime}: {count}").format(
                crime=self._crime_name(kind), count=self._number(count, 0)
            )
            for kind, count in ranked
        )

    def _crime_name(self, kind: str) -> str:
        if kind in CRIME_NAMES:
            return self._tl(CRIME_NAMES[kind])
        if kind.startswith(_ON_FOOT_PREFIX):
            crime = _from_symbol(kind.removeprefix(_ON_FOOT_PREFIX)).lower()
            return self._tl("On foot: {crime}").format(crime=crime)
        return _from_symbol(kind)

    def _faction_lines(self, by_faction: Mapping[str, Tally]) -> Iterable[StatLine]:
        """Most kills first; beyond ``FACTIONS_SHOWN``, the others in one line."""
        ranked = sorted(by_faction.items(), key=lambda item: (-item[1].kills, -item[1].credits))
        for faction, tally in ranked[:FACTIONS_SHOWN]:
            label = self._tl("Against {faction}").format(faction=faction)
            yield StatLine(label, self._kills_text(tally))
        others = ranked[FACTIONS_SHOWN:]
        if others:
            label = self._tl("Against {count} other factions").format(
                count=self._number(len(others), 0)
            )
            yield StatLine(label, self._kills_text(sum((t for _, t in others), Tally())))

    def _kills_text(self, tally: Tally) -> str:
        if tally.kills == 1:
            template = self._tl("{kills} kill, {credits}")
        else:
            template = self._tl("{kills} kills, {credits}")
        return template.format(
            kills=self._number(tally.kills, 0), credits=self._credits(tally.credits)
        )

    def _segment_text(self, segment: SegmentStats) -> str:
        return self._tl("{duration}, kills: {kills}").format(
            duration=format_duration(segment.duration, self._tl),
            kills=self._number(segment.tally.kills, 0),
        )

    def _average_line(self, average: SiteAverage) -> StatLine:
        rates = self._tl("{kills} kills/h, {credits}/h").format(
            kills=self._number(average.kills_per_hour, 1),
            credits=self._credits(average.credits_per_hour),
        )
        return StatLine(self._tl(SITE_NAMES[average.site]), rates)

    def _tally_text(self, tally: Tally) -> str:
        return self._tl("kills: {kills}, {credits}").format(
            kills=self._number(tally.kills, 0), credits=self._credits(tally.credits)
        )

    def _credits(self, credits: float) -> str:
        return format_credits(credits, self._tl, self._number)


def _from_symbol(symbol: str) -> str:
    """``carryingIllegalGoods`` → ``Carrying illegal goods``: a crime the table does not name."""
    words = _WORD.findall(symbol.replace("_", " ")) or [symbol]
    text = " ".join(word.lower() for word in words)
    return text[:1].upper() + text[1:]
