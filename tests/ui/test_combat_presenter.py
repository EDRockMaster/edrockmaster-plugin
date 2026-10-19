from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from edrockmaster.domain.combat.journal import VoucherKind
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatStarted,
    CombatStats,
    CombatUpdated,
    Crimes,
    SegmentStats,
    Tally,
)
from edrockmaster.domain.combat.sites import SiteType
from edrockmaster.domain.combat.vouchers import (
    HeldVoucher,
    PastJournals,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.infrastructure.strings_catalogue import translator
from edrockmaster.ui.combat_presenter import SITE_NAMES, CombatPresenter
from edrockmaster.ui.panel_model import PanelModel

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
CZ = SiteType.CONFLICT_ZONE_HIGH
NOTHING = Tally()
NO_CRIME = Crimes()


def segment(
    minutes: float = 30, site: SiteType = SiteType.RES_HAZARDOUS, **tally: int
) -> SegmentStats:
    values = {"kills": 6, "bounty_credits": 900_000}
    values.update(tally)
    return SegmentStats(site, T0, timedelta(minutes=minutes), Tally(**values))


def stats(
    *segments: SegmentStats,
    current: bool = True,
    miscellaneous: Tally = NOTHING,
    crimes: Crimes = NO_CRIME,
    by_victim_faction: dict[str, Tally] | None = None,
) -> CombatStats:
    segments = segments or (segment(),)
    return CombatStats(
        started_at=T0,
        segments=segments,
        current=segments[-1] if current else None,
        miscellaneous=miscellaneous,
        crimes=crimes,
        by_victim_faction=MappingProxyType(by_victim_faction or {}),
    )


READ = PastJournals(read=3, total=3)
LAVIGNY = "Lavigny's Legion"


def held(faction: str, amount: int, kind: VoucherKind = VoucherKind.BOUNTY) -> HeldVoucher:
    return HeldVoucher(kind, faction, amount, datetime(2026, 10, 14, 20, 0, tzinfo=UTC))


def vouchers(*held_vouchers: HeldVoucher, past: PastJournals = READ) -> VouchersUpdated:
    return VouchersUpdated(Vouchers(held_vouchers), past)


def value(model: PanelModel, label: str) -> str:
    [line] = [line for line in model.lines if line.label == label]
    return line.value


def labels(model: PanelModel) -> list[str]:
    return [line.label for line in model.lines]


@pytest.fixture
def presenter() -> CombatPresenter:
    return CombatPresenter()


def test_nothing_to_show_before_any_combat(presenter: CombatPresenter) -> None:
    assert presenter.render() == PanelModel(
        status="No combat session", lines=(), alert=None, can_reset=False
    )


def test_on_a_combat_site(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats())])
    assert model.status == "RES, hazardous"
    assert model.can_reset
    assert model.alert is None
    assert labels(model) == [
        "Active time",
        "Kills",
        "Bounties earned",
        "This site",
        "RES, hazardous",
    ]
    assert value(model, "Active time") == "30 min"
    assert value(model, "Kills") == "6"
    assert value(model, "Bounties earned") == "900,000 CR"
    assert value(model, "This site") == "30 min, kills: 6"
    assert value(model, "RES, hazardous") == "12.0 kills/h, 1,800,000 CR/h"


def test_a_ground_conflict_zone_shows_its_settlement(presenter: CombatPresenter) -> None:
    ground = SegmentStats(
        SiteType.GROUND_CONFLICT_ZONE, T0, timedelta(minutes=15), Tally(kills=9), "Pak's Habitat"
    )
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(ground))])
    assert model.status == "Ground conflict zone: Pak's Habitat"
    assert value(model, "Ground conflict zone") == "36.0 kills/h, 0 CR/h"


@pytest.mark.parametrize("site", list(SiteType))
def test_every_site_type_has_a_name(presenter: CombatPresenter, site: SiteType) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(segment(site=site)))])
    assert model.status == SITE_NAMES[site]


def test_between_sites(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(current=False))])
    assert model.status == "Combat"
    assert "This site" not in labels(model)


def test_one_average_per_site_type(presenter: CombatPresenter) -> None:
    conflict = segment(60, CZ, bounty_credits=0, bond_credits=600_000, kills=20)
    model = presenter.apply([CombatUpdated(stats(segment(), conflict, current=False))])
    assert value(model, "RES, hazardous") == "12.0 kills/h, 1,800,000 CR/h"
    assert value(model, "Conflict zone, high") == "20.0 kills/h, 600,000 CR/h"
    assert value(model, "Active time") == "1 h 30 min"


def test_miscellaneous_kills(presenter: CombatPresenter) -> None:
    misc = Tally(kills=1, bounty_credits=370_130)
    model = presenter.apply([CombatUpdated(stats(miscellaneous=misc))])
    assert value(model, "Miscellaneous") == "kills: 1, 370,130 CR"
    assert value(model, "Kills") == "7"


def test_only_miscellaneous_kills_show_no_active_time(presenter: CombatPresenter) -> None:
    misc = Tally(kills=1, bounty_credits=370_130)
    model = presenter.apply([CombatUpdated(CombatStats(T0, (), None, misc, Crimes()))])
    assert labels(model) == ["Kills", "Bounties earned", "Miscellaneous"]


def test_crimes(presenter: CombatPresenter) -> None:
    crimes = Crimes(count=2, fines=100, bounties=400, by_kind=MappingProxyType({"assault": 2}))
    model = presenter.apply([CombatUpdated(stats(crimes=crimes))])
    assert value(model, "Fines") == "100 CR"
    assert value(model, "Bounty on you") == "400 CR"
    assert "Fines" not in labels(presenter.apply([CombatUpdated(stats())]))


def test_crimes_by_kind_most_frequent_first(presenter: CombatPresenter) -> None:
    by_kind = {"recklessWeaponsDischarge": 1, "assault": 2}
    crimes = Crimes(count=3, fines=100, by_kind=MappingProxyType(by_kind))
    model = presenter.apply([CombatUpdated(stats(crimes=crimes))])
    assert value(model, "Crimes") == "Assault: 2, Reckless weapons discharge: 1"
    assert "Crimes" not in labels(presenter.apply([CombatUpdated(stats())]))


def test_a_crime_the_application_does_not_know_stays_readable(presenter: CombatPresenter) -> None:
    by_kind = {"onFoot_carryingIllegalGoods": 1, "collidedAtSpeedInNoFireZone_hulldamage": 1}
    crimes = Crimes(count=2, by_kind=MappingProxyType(by_kind))
    model = presenter.apply([CombatUpdated(stats(crimes=crimes))])
    assert value(model, "Crimes") == (
        "On foot: carrying illegal goods: 1, Collision at speed in a no-fire zone, hull damaged: 1"
    )


def test_crimes_in_french() -> None:
    presenter = CombatPresenter(translator("fr"))
    crimes = Crimes(count=1, fines=100, by_kind=MappingProxyType({"recklessWeaponsDischarge": 1}))
    model = presenter.apply([CombatUpdated(stats(crimes=crimes))])
    assert value(model, "Délits") == "Tir imprudent : 1"


def test_kills_by_victim_faction_most_kills_first(presenter: CombatPresenter) -> None:
    by_faction = {
        "Empire": Tally(kills=1, bond_credits=50_000),
        "Pirates": Tally(kills=3, bounty_credits=300_000),
    }
    model = presenter.apply([CombatUpdated(stats(by_victim_faction=by_faction))])
    assert labels(model)[-2:] == ["Against Pirates", "Against Empire"]
    assert value(model, "Against Pirates") == "3 kills, 300,000 CR"
    assert value(model, "Against Empire") == "1 kill, 50,000 CR"


def test_beyond_three_factions_the_others_add_up(presenter: CombatPresenter) -> None:
    by_faction = {
        name: Tally(kills=kills, bounty_credits=kills * 10_000)
        for name, kills in (("A", 5), ("B", 4), ("C", 3), ("D", 2), ("E", 1))
    }
    model = presenter.apply([CombatUpdated(stats(by_victim_faction=by_faction))])
    assert [label for label in labels(model) if label.startswith("Against")] == [
        "Against A",
        "Against B",
        "Against C",
        "Against 2 other factions",
    ]
    assert value(model, "Against 2 other factions") == "3 kills, 30,000 CR"


def test_shared_kills_and_combat_bonds_appear_when_present(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatUpdated(stats(segment(shared_kills=2, bond_credits=120_000)))])
    assert value(model, "Kills") == "6 (2 shared)"
    assert value(model, "Combat bonds earned") == "120,000 CR"


def test_bounties_are_left_out_when_only_combat_bonds_were_earned(
    presenter: CombatPresenter,
) -> None:
    model = presenter.apply(
        [CombatUpdated(stats(segment(site=CZ, bounty_credits=0, bond_credits=224_467)))]
    )
    assert "Bounties earned" not in labels(model)
    assert value(model, "Combat bonds earned") == "224,467 CR"


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        (CombatEndReason.GAME_CLOSED, "Combat session ended: game closed"),
        (CombatEndReason.DIED, "Combat session ended: ship destroyed"),
        (CombatEndReason.MANUAL, "Combat session ended: reset"),
    ],
)
def test_ended_combat_keeps_its_statistics(
    presenter: CombatPresenter, reason: CombatEndReason, status: str
) -> None:
    model = presenter.apply([CombatStarted(T0), CombatEnded(T0, reason, stats(current=False))])
    assert model.status == status
    assert not model.can_reset
    assert value(model, "Kills") == "6"


def test_one_kind_of_unredeemed_vouchers_is_one_line(presenter: CombatPresenter) -> None:
    model = presenter.apply([vouchers(held(LAVIGNY, 33_552_700))])
    assert [(line.label, line.value) for line in model.lines] == [
        ("Unredeemed bounties, Lavigny's Legion", "33,552,700 CR, since 14 October 2026")
    ]


def test_several_add_up_then_come_one_by_one_the_largest_first(
    presenter: CombatPresenter,
) -> None:
    model = presenter.apply(
        [
            vouchers(
                held("Olker General Solutions", 46_700),
                held(LAVIGNY, 33_552_700),
                held(LAVIGNY, 100_000, VoucherKind.COMBAT_BOND),
            )
        ]
    )
    assert [(line.label, line.value) for line in model.lines] == [
        ("Unredeemed", "33,699,400 CR"),
        ("Unredeemed bounties, Lavigny's Legion", "33,552,700 CR, since 14 October 2026"),
        ("Unredeemed combat bonds, Lavigny's Legion", "100,000 CR, since 14 October 2026"),
        ("Unredeemed bounties, Olker General Solutions", "46,700 CR, since 14 October 2026"),
    ]


def test_beyond_three_the_others_add_up(presenter: CombatPresenter) -> None:
    model = presenter.apply([vouchers(*(held(f"Faction {n}", 1_000 * n) for n in range(1, 6)))])
    assert labels(model)[-1] == "Unredeemed from 2 other factions"
    assert value(model, "Unredeemed from 2 other factions") == "3,000 CR"


def test_without_vouchers_once_past_journals_are_read_it_says_none(
    presenter: CombatPresenter,
) -> None:
    presenter.apply([vouchers(held(LAVIGNY, 1_000))])
    assert [(line.label, line.value) for line in presenter.apply([vouchers()]).lines] == [
        ("Unredeemed", "none")
    ]


def test_without_vouchers_while_past_journals_are_read_it_says_nothing_yet(
    presenter: CombatPresenter,
) -> None:
    model = presenter.apply([vouchers(past=PastJournals(1, 2))])
    assert labels(model) == ["Past journals"]


def test_reading_past_journals_is_shown_until_done(presenter: CombatPresenter) -> None:
    model = presenter.apply([vouchers(held(LAVIGNY, 1_000), past=PastJournals(120, 860))])
    assert value(model, "Past journals") == "reading: 120 / 860"
    assert labels(model)[-1] == "Past journals"
    assert "Past journals" not in labels(presenter.apply([vouchers()]))


def test_unredeemed_vouchers_in_french() -> None:
    presenter = CombatPresenter(translator("fr"))
    model = presenter.apply([vouchers(held(LAVIGNY, 1_000), past=PastJournals(1, 2))])
    assert [(line.label, line.value) for line in model.lines] == [
        ("Primes non encaissées, Lavigny's Legion", "1,000 CR, depuis le 14 octobre 2026"),
        ("Anciens journaux", "lecture : 1 / 2"),
    ]
    assert [(line.label, line.value) for line in presenter.apply([vouchers()]).lines] == [
        ("Non encaissé", "aucun")
    ]


def test_render_rebuilds_texts_in_the_current_language() -> None:
    language = {"prefix": ""}
    presenter = CombatPresenter(translate=lambda text: language["prefix"] + text)
    presenter.apply([CombatStarted(T0), CombatUpdated(stats())])
    language["prefix"] = "fr:"
    assert presenter.render().status == "fr:RES, hazardous"
