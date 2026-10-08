import pytest

from edrockmaster.ui.panel_model import LocalDataNotice, notice_text


@pytest.mark.parametrize(
    ("notice", "start"),
    [
        (LocalDataNotice.RESET, "Local data could not be read"),
        (LocalDataNotice.UNAVAILABLE, "Local data is unavailable"),
    ],
)
def test_each_local_data_notice_has_its_text(notice: LocalDataNotice, start: str) -> None:
    assert notice_text(notice, lambda text: text).startswith(start)
