import pytest

from collections import namedtuple

from sdvxparser.parser.vox import VOXParser

NoteCount = namedtuple("NoteCount", ["chip", "long", "vol"])

test_data: dict[str, NoteCount] = {}


@pytest.mark.parametrize("fn, expected", test_data.items())
def test_chain_counts(fn: str, expected: NoteCount):
    with open(fn, "r", encoding="utf-8") as f:
        chart_data = VOXParser().parse(f)

    assert (
        NoteCount(
            chart_data.chart_info.chip_notecount,
            chart_data.chart_info.long_notecount,
            chart_data.chart_info.vol_notecount,
        )
        == expected
    )
