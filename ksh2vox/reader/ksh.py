import dataclasses
import io
import pprint
import re

from fractions import Fraction

from ..classes import BTInfo, ChartInfo, TimePoint

BAR_LINE = '--\n'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:@(\(|\)|<|>)|S>|S<)?')
LASER_POSITION = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno'


@dataclasses.dataclass()
class KSHLine:
    bt_a: int
    bt_b: int
    bt_c: int
    bt_d: int
    fx_l: int
    fx_r: int
    vol_l: str
    vol_r: str
    extra: str


def line_to_data(s: str) -> KSHLine:
    return KSHLine(
        int(s[0]), int(s[1]), int(s[2]), int(s[3]),
        int(s[5]), int(s[6]),
        s[8], s[9],
        s[10:])


def read_ksh(f: io.TextIOBase) -> ChartInfo:
    chart = ChartInfo()

    # Metadata read
    for line in f:
        if line == BAR_LINE:
            break

    measure: list[str] = []
    measure_count: int = 0
    durations: list[Fraction] = [Fraction(0)] * 6
    for line in f:
        if line == BAR_LINE:
            print(f'measure {measure_count}: {len(measure)}')
            for s, subline in enumerate(measure):
                current_time = TimePoint(measure_count, s, len(measure))
                line_info = line_to_data(subline)
                for attr in ['bt_a', 'bt_b', 'bt_c', 'bt_d']:
                    bt_value: int = getattr(line_info, attr)
                    if bt_value == 0:
                        pass
                    elif bt_value == 1:
                        pass
                    elif bt_value == 2:
                        pass
                    else:
                        raise ValueError(f'unrecognized BT value (got {bt_value})')

            measure_count += 1
            measure = []
            continue

        match = CHART_REGEX.search(line)
        if match is None:
            continue

        measure.append(match.group(0))

    return chart
