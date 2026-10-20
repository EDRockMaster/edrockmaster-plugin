"""The galaxy's prices, the answers without the core (ADR 0047)."""

from datetime import UTC, datetime

from edrockmaster.application.community import Failed, Found, Source, Unavailable
from edrockmaster.desktop.trade_view import prices_refused, prices_view
from edrockmaster.domain.commodities import GalaxyPrices, PriceRange

READ = datetime.fromisoformat("2026-10-20T14:00:00+02:00")


def test_the_prices_both_ways() -> None:
    prices = GalaxyPrices(
        buy=None,
        sell=PriceRange(2064, 56364, 375928),
        computed_at=datetime.fromisoformat("2026-09-07T07:46:13+02:00"),
    )
    assert prices_view(Found(prices, Source.ARDENT, READ, Unavailable.BUSY)) == {
        "status": "found",
        "source": "ardent",
        "readAt": "2026-10-20T12:00:00+00:00",
        "unavailable": "busy",
        "buy": None,
        "sell": {"lowest": 2064, "average": 56364, "highest": 375928},
        "computedAt": datetime(2026, 9, 7, 5, 46, 13, tzinfo=UTC).isoformat(),
    }


def test_a_failed_source_gives_no_prices() -> None:
    assert prices_view(Failed(Source.ARDENT, Unavailable.OFF)) == {
        "status": "off",
        "source": "ardent",
        "readAt": None,
        "unavailable": None,
        "buy": None,
        "sell": None,
        "computedAt": None,
    }
    assert prices_refused("invalid") == {
        "status": "invalid",
        "source": None,
        "readAt": None,
        "unavailable": None,
        "buy": None,
        "sell": None,
        "computedAt": None,
    }
