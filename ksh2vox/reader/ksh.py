import fractions
import io

from ..classes import ChartInfo, TimePoint


def read_ksh(f: io.TextIOBase) -> ChartInfo:
    chart = ChartInfo()

    chart.bpms[1] = 0
