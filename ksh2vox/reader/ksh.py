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
    SpinType,
    TimePoint,
    TimeSignature,
    VolInfo,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
LASER_POSITION = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno'
FX_STATE_MAP = {'0': '0', '1': '2', '2': '1'}


@dataclasses.dataclass
class _HoldInfo:
    start: TimePoint
    duration: Fraction = Fraction(0)


@dataclasses.dataclass
class _LastVolInfo:
    when: TimePoint
    duration: Fraction
    prev_vol: VolInfo


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
    holds: dict[str, _HoldInfo] = {}
    is_continued_segment = {
        'vol_l': False,
        'vol_r': False,
    }
    current_timesig = TimeSignature()
    last_vol_data: dict[str, _LastVolInfo] = {}
    for line_no, full_line in enumerate(f):
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
                                    holds[input] = _HoldInfo(current_time)
                                holds[input].duration += Fraction(1, len(measure_lines))
                        # VOL handled differently
                        elif input.startswith('vol'):
                            # Extend duration
                            if state == '-' and input in last_vol_data:
                                del last_vol_data[input]
                            elif input in last_vol_data:
                                last_vol_data[input].duration += Fraction(1 * current_timesig.upper, subdivision_count * current_timesig.lower)
                                if last_vol_data[input].duration > Fraction(1, 32):
                                    del last_vol_data[input]

                            # Handle incoming laser
                            if state == '-':
                                is_continued_segment[input] = False
                            elif state == ':':
                                pass
                            else:
                                vol_position = Fraction(LASER_POSITION.index(state), len(LASER_POSITION) - 1)
                                if (input in last_vol_data and
                                    last_vol_data[input].duration <= Fraction(1, 32) and
                                    last_vol_data[input].prev_vol.start != vol_position):
                                    last_vol_info = last_vol_data[input]
                                    note_data_vol[input][last_vol_info.when] = VolInfo(
                                        last_vol_info.prev_vol.start,
                                        vol_position,
                                        is_new_segment=last_vol_info.prev_vol.is_new_segment)
                                else:
                                    if is_continued_segment[input]:
                                        note_data_vol[input][current_time] = VolInfo(vol_position, vol_position, is_new_segment=False)
                                    else:
                                        note_data_vol[input][current_time] = VolInfo(vol_position, vol_position)
                                last_vol_data[input] = _LastVolInfo(
                                    current_time,
                                    Fraction(0),
                                    VolInfo(vol_position, vol_position, is_new_segment=not is_continued_segment[input]))
                                is_continued_segment[input] = True
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

        warnings.warn(f'unrecognized line ({line_no}) ignored: {line}')

    # Apply spins
    for timepoint, spin_state in spin_info.items():
        spin_type, spin_duration_str = spin_state[:2], spin_state[2:]
        if spin_type[0] == 'S':
            warnings.warn(f'ignoring swing effect at {timepoint}', ParserWarning)
            continue
        if timepoint not in note_data_vol['vol_l'] and timepoint not in note_data_vol['vol_r']:
            warnings.warn(f'found spin data without associated laser data at {timepoint}', ParserWarning)
            continue

        # NOTE: spin duration is given as number of 1/192nds regardless of time signature.
        # spins in KSM persists a little longer -- roughly 1.33x times of its given length.
        # assuming 4/4 time signature, a spin duration of 192 lasts a whole measure (and a
        # bit more), so you multiply this by 4 to get the number of beats the spin will last.
        # ultimately, that means the duration is multiplied by 16/3 and rounded.
        # TODO: test if the number is actually in beats or if it depends on the time sig.
        spin_duration = int(spin_duration_str)
        if timepoint in note_data_vol['vol_l']:
            vol_data = note_data_vol['vol_l'][timepoint]
            if vol_data.start < vol_data.end:
                if spin_type[1] == ')':
                    vol_data.spin_type = SpinType.SINGLE_SPIN
                    # TODO: check if spin duration must be a whole number
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
                elif spin_type[1] == '>':
                    vol_data.spin_type = SpinType.HALF_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
            elif vol_data.start > vol_data.end:
                if spin_type[1] == '(':
                    vol_data.spin_type = SpinType.SINGLE_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
                elif spin_type[1] == '<':
                    vol_data.spin_type = SpinType.HALF_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
        elif timepoint in note_data_vol['vol_r']:
            vol_data = note_data_vol['vol_r'][timepoint]
            if vol_data.start < vol_data.end:
                if spin_type[1] == ')':
                    vol_data.spin_type = SpinType.SINGLE_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
                elif spin_type[1] == '>':
                    vol_data.spin_type = SpinType.HALF_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
            elif vol_data.start > vol_data.end:
                if spin_type[1] == '(':
                    vol_data.spin_type = SpinType.SINGLE_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue
                elif spin_type[1] == '<':
                    vol_data.spin_type = SpinType.HALF_SPIN
                    vol_data.spin_duration = round(Fraction(spin_duration, 192) * 16 / 3)
                    continue

        warnings.warn(f'cannot match spin at {timepoint} with any slam', ParserWarning)

    return chart
