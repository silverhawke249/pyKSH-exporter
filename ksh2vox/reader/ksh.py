import dataclasses
import io
import re
import warnings

from fractions import Fraction

from ..classes import (
    BTInfo,
    ChartInfo,
    FXInfo,
    ParserWarning,
    TimePoint,
    TimeSignature,
    VolInfo,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
LASER_POSITION = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno'
FX_STATE_MAP = {'0': '0', '1': '2', '2': '1'}


@dataclasses.dataclass
class _DurationInfo:
    start: TimePoint
    duration: Fraction = Fraction(0)


@dataclasses.dataclass
class _LastVolInfo:
    when: TimePoint
    duration: Fraction


def process_ksh_line(s: str) -> dict[str, str]:
    bt, fx, vol = s.split('|')
    return {
        'bt_a': bt[0],
        'bt_b': bt[1],
        'bt_c': bt[2],
        'bt_d': bt[3],
        'fx_l': FX_STATE_MAP[fx[0]],
        'fx_r': FX_STATE_MAP[fx[0]],
        'vol_l': vol[0],
        'vol_r': vol[1],
        'spin': vol[2:],
    }


def read_ksh(f: io.TextIOBase) -> ChartInfo:
    chart = ChartInfo()
    chart.time_sigs[TimePoint(0, 0, 1)] = TimeSignature()

    # Metadata read
    chart_metadata: dict[str, str] = {}
    for line in f:
        line = line.strip()
        if line == BAR_LINE:
            break
        if '=' not in line:
            warnings.warn(f'unrecognized line: {line}', ParserWarning)
            continue

        key, value = line.split('=', 1)
        if key in chart_metadata.keys():
            warnings.warn(f'ignoring extra metadata: {line}', ParserWarning)
            continue

        chart_metadata[key] = value

    # Read note data
    # Counters
    measure_lines: list[str] = []
    measure_count = 0
    subdivision_count = 0
    # Reference to note data stored in dicts for easier access
    note_data_bt = {
        'bt_a': chart.note_data.bt_a,
        'bt_b': chart.note_data.bt_b,
        'bt_c': chart.note_data.bt_c,
        'bt_d': chart.note_data.bt_d,
    }
    note_data_fx = {
        'fx_l': chart.note_data.fx_l,
        'fx_r': chart.note_data.fx_r,
    }
    note_data_vol = {
        'vol_l': chart.note_data.vol_l,
        'vol_r': chart.note_data.vol_r,
    }
    # Information with deferred processing
    spin_info: dict[TimePoint, str] = {}
    # Stateful information
    holds: dict[str, _DurationInfo] = {}
    vol_segment = {
        'vol_l': False,
        'vol_r': False,
    }
    current_timesig = TimeSignature()
    last_vol_data: dict[str, TimePoint | Fraction] = {}
    for full_line in f:
        # Handle comments
        full_line = full_line.strip()
        if '//' in full_line:
            line, comment = full_line.split('//', 1)
            line = line.strip()
            comment = comment.strip()
        else:
            line = full_line
            comment = ''

        # One complete measure
        if line == BAR_LINE:
            # Check time signatures that get pushed to the next measure
            if TimePoint(measure_count, 0, 1) in chart.time_sigs:
                current_timesig = chart.time_sigs[TimePoint(measure_count, 0, 1)]

            noteline_count = 0
            for subline in measure_lines:
                # Metadata
                if '=' in subline:
                    key, value = subline.split('=', 1)
                    if key == 'beat':
                        upper, lower = [int(v) for v in value.split('/')]
                        timesig = TimeSignature(upper, lower)
                        # Time signature changes can only occur at the start of a measure
                        # Changes not at the start of a measaure is pushed to the next measure
                        if noteline_count != 0:
                            chart.time_sigs[TimePoint(measure_count + 1, 0, 1)] = timesig
                        else:
                            chart.time_sigs[TimePoint(measure_count, 0, 1)] = timesig
                            current_timesig = timesig
                    # TODO: Check other metadata
                # Note data
                else:
                    adjusted_time = Fraction(noteline_count * current_timesig.upper, subdivision_count * current_timesig.lower)
                    current_time = TimePoint(measure_count, adjusted_time.numerator, adjusted_time.denominator)
                    subline_data = process_ksh_line(subline)
                    for input in subline_data.keys():
                        state = subline_data[input]
                        # BT and FX are handled similarly, just different data class
                        if input.startswith('bt') or input.startswith('fx'):
                            if state == '0' and input in holds.keys():
                                if input.startswith('bt'):
                                    note_data_bt[input][holds[input].start] = BTInfo(holds[input].duration)
                                elif input.startswith('fx'):
                                    note_data_fx[input][holds[input].start] = FXInfo(holds[input].duration, 0)
                                del holds[input]
                            elif state == '1':
                                if input.startswith('bt'):
                                    note_data_bt[input][current_time] = BTInfo(0)
                                elif input.startswith('fx'):
                                    note_data_fx[input][current_time] = FXInfo(0, 0)
                            elif state == '2':
                                if input not in holds.keys():
                                    holds[input] = _DurationInfo(current_time)
                                holds[input].duration += Fraction(1, len(measure_lines))
                        # VOL handled differently
                        elif input.startswith('vol'):
                            if state == '-':
                                vol_segment[input] = False
                            elif state == ':':
                                pass
                            else:
                                vol_position = Fraction(LASER_POSITION.index(state), len(LASER_POSITION) - 1)
                                if vol_segment[input]:
                                    note_data_vol[input][current_time] = VolInfo(vol_position, vol_position, is_new_segment=False)
                                else:
                                    note_data_vol[input][current_time] = VolInfo(vol_position, vol_position)
                                vol_segment[input] = True
                        # Spin handling is deferred
                        elif input == 'spin':
                            if state != '':
                                spin_info[current_time] = state

                    noteline_count += 1

            measure_count += 1
            measure_lines = []
            subdivision_count = 0
            continue

        # Metadata
        if '=' in line:
            measure_lines.append(line)
            continue

        # Notedata
        match = CHART_REGEX.search(line)
        if match:
            measure_lines.append(match.group(0))
            subdivision_count += 1
            continue

    '''
    # Convert short lasers to slams
    for vol_data in note_data_vol.values():
        # These were inserted in order, so there's no need to sort
        timepoints = list(vol_data.keys())
        for i in range(len(timepoints) - 1):
            cur_time = timepoints[i]
            timesig = TimeSignature()
            # This is guaranteed to finish anyway
            for m in range(cur_time.measure, -1, -1):
                if TimePoint(m, 0, 1) in chart.time_sigs:
                    timesig = chart.time_sigs[TimePoint(m, 0, 1)]
                    break
            cur_dist_to_end = Fraction(timesig.upper, timesig.lower) - cur_time.position

            next_time = timepoints[i + 1]
            if next_time.measure == cur_time.measure:
                next_dist_to_end = Fraction(timesig.upper, timesig.lower) - next_time.position
                if abs(cur_dist_to_end - next_dist_to_end) < Fraction(1, 32):
    '''

    return chart
