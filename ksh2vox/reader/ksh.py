import dataclasses
import re
import warnings

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from ..classes import (
    BTInfo,
    ChartInfo,
    DifficultySlot,
    FilterType,
    FXInfo,
    ParserWarning,
    SongInfo,
    SpinType,
    TimePoint,
    TimeSignature,
    VolInfo,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
LASER_POSITION = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno'
FX_STATE_MAP = {'0': '0', '1': '2', '2': '1'}
INPUT_BT  = ['bt_a', 'bt_b', 'bt_c', 'bt_d']
INPUT_FX  = ['fx_l', 'fx_r']
INPUT_VOL = ['vol_l', 'vol_r']
FILTER_TYPE_MAP = {
    'peak': FilterType.PEAK,
    'lpf1': FilterType.LPF,
    'hpf1': FilterType.HPF,
    'bitc': FilterType.BITCRUSH,
}


@dataclasses.dataclass
class _HoldInfo:
    start: TimePoint
    duration: Fraction = Fraction(0)


@dataclasses.dataclass
class _LastVolInfo:
    when: TimePoint
    duration: Fraction
    prev_vol: VolInfo


# Song metadata in XML:
# - ID
# - Title
# - Title (yomigana)
# - Artist
# - Artist (yomigana)
# - ASCII label
# - Max BPM
# - Min BPM
# - Release date
# - Volume
# - In-game background
# - Genre (FLOOR/TOUHOU/etc)
# - is_fixed (?)
# - Version (1-6)
# - demo_pri (show this in attract screen?)
# - inf_ver (INF/GRV/HVN/VVD/XCD)
# We can only derive title/artist/BPM info from KSH, the rest must be user input

# Chart metadata in XML:
# - Level
# - Illustrator
# - Effector
# - Price (-1)
# - Limited (3)


@dataclasses.dataclass(eq=False)
class KSHParser:
    # Init variables
    file: dataclasses.InitVar[TextIO]

    # Private variables
    _ksh_path: Path = dataclasses.field(init=False)

    _raw_metadata: list[str] = dataclasses.field(init=False, repr=False)
    _raw_notedata: list[str] = dataclasses.field(init=False, repr=False)
    _raw_definitions: list[str] = dataclasses.field(init=False, repr=False)

    _song_info : SongInfo  = dataclasses.field(init=False)
    _chart_info: ChartInfo = dataclasses.field(init=False)

    _fx_list: list[str]            = dataclasses.field(default_factory=list, init=False, repr=False)

    # Stateful data for notechart parsing
    _cur_timesig: TimeSignature = dataclasses.field(default=TimeSignature(), init=False, repr=False)
    _cur_filter : FilterType    = dataclasses.field(default=FilterType.PEAK, init=False, repr=False)

    _filter_changed: bool = dataclasses.field(default=False, init=False, repr=False)

    _holds : dict[str, _HoldInfo] = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_fx: dict[str, str]       = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_se: dict[str, int]       = dataclasses.field(default_factory=dict, init=False, repr=False)

    _bts : dict[str, dict[TimePoint, BTInfo]]  = dataclasses.field(init=False, repr=False)
    _fxs : dict[str, dict[TimePoint, FXInfo]]  = dataclasses.field(init=False, repr=False)
    _vols: dict[str, dict[TimePoint, VolInfo]] = dataclasses.field(init=False, repr=False)

    def __post_init__(self, file: TextIO):
        self._ksh_path = Path(file.name).resolve()

        self._raw_metadata = []
        for line in file:
            line = line.strip()
            if line == BAR_LINE:
                break
            self._raw_metadata.append(line.strip())

        self._raw_notedata = [line.strip() for line in file]

        self._raw_definitions = []
        while True:
            line = self._raw_notedata[-1]
            if line == BAR_LINE:
                break
            self._raw_definitions.append(line)
            self._raw_notedata.pop()

        self._raw_definitions.reverse()

        self._parse_metadata()
        self._parse_notedata()
        self._parse_definitions()

    def _parse_metadata(self) -> None:
        self._song_info = SongInfo()
        self._chart_info = ChartInfo()

        for line_no, line in enumerate(self._raw_metadata):
            if '=' not in line:
                warnings.warn(f'unrecognized line at line {line_no + 1}: {line}')
            key, value = line.split('=', 1)
            if key == 'title':
                self._song_info.title = value
            elif key == 'artist':
                self._song_info.artist = value
            elif key == 'effect':
                self._chart_info.effector = value
            elif key == 'jacket':
                self._chart_info.jacket_path = value
            elif key == 'illustrator':
                self._chart_info.illustrator = value
            elif key == 'difficulty':
                if value == 'light':
                    self._chart_info.difficulty = DifficultySlot.NOVICE
                elif value == 'challenge':
                    self._chart_info.difficulty = DifficultySlot.ADVANCED
                elif value == 'extended':
                    self._chart_info.difficulty = DifficultySlot.EXHAUST
                else:
                    self._chart_info.difficulty = DifficultySlot.MAXIMUM
            elif key == 'level':
                self._chart_info.level = int(value)
            elif key == 't':
                if '-' in value:
                    min_bpm_str, max_bpm_str = value.split('-')
                    self._song_info.min_bpm = Decimal(min_bpm_str)
                    self._song_info.max_bpm = Decimal(max_bpm_str)
                else:
                    bpm = Decimal(value)
                    self._song_info.min_bpm = bpm
                    self._song_info.max_bpm = bpm
                    self._chart_info.bpms[TimePoint(1, 0, 1)] = bpm
            elif key == 'beat':
                upper_str, lower_str = value.split('/')
                upper, lower = int(upper_str), int(lower_str)
                self._chart_info.time_sigs[TimePoint(1, 0, 1)] = TimeSignature(upper, lower)
                self._cur_timesig = TimeSignature(upper, lower)
            elif key == 'm':
                self._chart_info.music_path = value
            elif key == 'mvol':
                self._song_info.music_volume = int(value)
            elif key == 'o':
                self._chart_info.music_offset = int(value)
            elif key == 'po':
                self._chart_info.preview_start = int(value)
            elif key == 'filtertype':
                if value == 'peak':
                    self._chart_info.filter_types[TimePoint(1, 0, 1)] = FilterType.PEAK
                elif value == 'hpf1':
                    self._chart_info.filter_types[TimePoint(1, 0, 1)] = FilterType.HPF
                elif value == 'lpf1':
                    self._chart_info.filter_types[TimePoint(1, 0, 1)] = FilterType.LPF
                elif value == 'bitc':
                    self._chart_info.filter_types[TimePoint(1, 0, 1)] = FilterType.BITCRUSH
            elif key == 'ver':
                # You know, I should probably differentiate handling top/bottom zooms depending if
                # the version is >= 167 or not, but I'm most likely not going to fucking bother
                try:
                    version = int(value)
                    if version < 160:
                        raise ValueError(f'ksh file version too old (got {value})')
                except ValueError as e:
                    raise ValueError(f'ksh file version too old (got {value})') from e
            else:
                # Ignoring all other metadata
                pass

    def _parse_notedata(self) -> None:
        # Initialize these for chart parsing
        self._bts = {
            'bt_a': {},
            'bt_b': {},
            'bt_c': {},
            'bt_d': {},
        }
        self._fxs = {
            'fx_l': {},
            'fx_r': {},
        }
        self._vols = {
            'vol_l': {},
            'vol_r': {},
        }

        # Measure data
        line_no_offset   : int       = len(self._raw_metadata) + 1
        measure_data     : list[str] = []
        measure_number   : int       = 1
        subdivision_count: int       = 0
        for line_no, line in enumerate(self._raw_notedata):
            # Four types of lines in here:
            # 1. Note data
            match = CHART_REGEX.search(line)
            if match is not None:
                measure_data.append(match.group(0))
                subdivision_count += 1
            # 2. Metadata (BPM change, time signature change, FX specifier, etc)
            # Metadata is processed together with note data
            elif '=' in line:
                measure_data.append(line)
            # 3. Comments
            # Comments will be used to give extra data that's not supported by KSM
            elif line.startswith('//'):
                measure_data.append(line)
            # 4. Measure divider
            elif line == BAR_LINE:
                self._parse_measure(measure_data, measure_number, subdivision_count)
                measure_number   += 1
                measure_data      = []
                subdivision_count = 0
            else:
                warnings.warn(f'unrecognized line at line {line_no_offset + line_no + 1}: {line}')

    def _parse_measure(self, measure: list[str], m_no: int, m_linecount: int) -> None:
        # Check time signatures that get pushed to the next measure
        if TimePoint(m_no, 0, 1) in self._chart_info.time_sigs:
            self._cur_timesig = self._chart_info.time_sigs[TimePoint(m_no, 0, 1)]

        noteline_count = 0
        for line in measure:
            subdivision = Fraction(1 * self._cur_timesig.upper, m_linecount * self._cur_timesig.lower)
            cur_subdiv  = noteline_count * subdivision
            cur_time    = TimePoint(m_no, cur_subdiv.numerator, cur_subdiv.denominator)

            # 1. Metadata
            if '=' in line:
                key, value = line.split('=', 1)
                if key == 't':
                    pass
                elif key == 'beat':
                    pass
                elif key == 'stop':
                    pass
                elif key == 'tilt':
                    pass
                elif key == 'zoom_top':
                    pass
                elif key == 'zoom_bottom':
                    pass
                elif key == 'center_split':
                    pass
                elif key in ['laserrange_l', 'laserrange_r']:
                    pass
                elif key in ['fx-l', 'fx-r']:
                    key = key.replace('-', '_')
                    if value and value not in self._fx_list:
                        self._fx_list.append(value)
                    if key in self._set_fx:
                        # Send warning only if:
                        # - effect is not null
                        # - currently stored effect is not the null effect
                        # - currently stored effect is different from incoming effect
                        if value and self._set_fx[key] and self._set_fx[key] != value:
                            warnings.warn(f'ignoring effect {value} assigned to {key} that already has an assigned '
                                          f'effect {self._set_fx[key]} at m{m_no}', ParserWarning)
                        continue
                    self._set_fx[key] = value
                elif key in ['fx-l_se', 'fx-r_se']:
                    key = key[:4]
                    key = key.replace('-', '_')
                    value = value.split(';')[0]
                    if value.endswith('.wav'):
                        value = value[:-4]
                    try:
                        self._set_se[key] = int(value)
                    except ValueError:
                        pass
                elif key == 'filtertype':
                    if value in FILTER_TYPE_MAP:
                        self._cur_filter = FILTER_TYPE_MAP[value]
                        self._filter_changed = True
                    else:
                        # Handle track auto tab here
                        pass
                elif ':' in key:
                    # This is for filter settings
                    # > filter:[filter_name]:[parameter]=[value]
                    # Technically FX parameters can also be changed here but like no one uses that
                    pass
                else:
                    # Ignoring all other metadata
                    pass
            # 2. Comment
            elif line.startswith('//'):
                # Remove initial `//`
                line = line[2:]
                if '=' in line:
                    # Define custom commands here
                    pass
            # 3. Notedata
            else:
                bts, fxs, vols_and_spin = line.split('|')
                vols = vols_and_spin[:2]
                spin = vols_and_spin[2:]
                for bt, state in zip(INPUT_BT, bts):
                    if state == '0' and bt in self._holds:
                        self._bts[bt][self._holds[bt].start] = BTInfo(self._holds[bt].duration)
                        del self._holds[bt]
                    if state == '1':
                        if bt in self._holds:
                            warnings.warn(f'improperly terminated hold at {cur_time}', ParserWarning)
                            del self._holds[bt]
                        self._bts[bt][cur_time] = BTInfo(0)
                    if state == '2':
                        if bt not in self._holds:
                            self._holds[bt] = _HoldInfo(cur_time)
                        self._holds[bt].duration += subdivision
                for fx, state in zip(INPUT_FX, fxs):
                    if state == '0' and fx in self._holds:
                        fx_effect = self._set_fx.get(fx, None)
                        if fx in self._set_fx:
                            del self._set_fx[fx]
                        if not fx_effect:
                            fx_index = 0
                        else:
                            fx_index = self._fx_list.index(fx_effect) + 2
                        self._fxs[fx][self._holds[fx].start] = FXInfo(self._holds[fx].duration, fx_index)
                        del self._holds[fx]
                    if state == '1':
                        if fx not in self._holds:
                            self._holds[fx] = _HoldInfo(cur_time)
                        self._holds[fx].duration += subdivision
                    if state == '2':
                        if fx in self._holds:
                            warnings.warn(f'improperly terminated hold at {cur_time}', ParserWarning)
                            del self._holds[fx]
                        se_index = self._set_se.get(fx, 0)
                        self._fxs[fx][cur_time] = FXInfo(0, se_index)
                    # Clean up -- FX SE only affects the FX chip immediately after
                    if fx in self._set_se:
                        del self._set_se[fx]
                for vol, state in zip(INPUT_VOL, vols):
                    pass

                noteline_count += 1

        # Store note data in chart
        for k, v1 in self._bts.items():
            setattr(self._chart_info.note_data, k, v1)
        for k, v2 in self._fxs.items():
            setattr(self._chart_info.note_data, k, v2)
        for k, v3 in self._vols.items():
            setattr(self._chart_info.note_data, k, v3)

    def _parse_definitions(self):
        pass


def process_ksh_line(s: str) -> dict[str, str]:
    bt, fx, vol = s.split('|')
    return {
        'bt_a': bt[0],
        'bt_b': bt[1],
        'bt_c': bt[2],
        'bt_d': bt[3],
        'fx_l': FX_STATE_MAP[fx[0]],
        'fx_r': FX_STATE_MAP[fx[1]],
        'vol_l': vol[0],
        'vol_r': vol[1],
        'spin': vol[2:],
    }


def read_ksh(f: TextIO) -> ChartInfo:
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
    measure_count            = 0
    subdivision_count        = 0
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
    fx_list  : list[str]            = ['']
    # Stateful information
    holds : dict[str, _HoldInfo] = {}
    fx_set: dict[str, int]       = {}
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
                        # Changes not at the start of a measure is pushed to the next measure
                        if noteline_count != 0:
                            chart.time_sigs[TimePoint(measure_count + 1, 0, 1)] = timesig
                        else:
                            chart.time_sigs[TimePoint(measure_count, 0, 1)] = timesig
                            current_timesig = timesig
                    elif key in ['fx-l', 'fx-r']:
                        key = key.replace('-', '_')
                        if value and value not in fx_list:
                            fx_list.append(value)
                        if key in fx_set:
                            # Send warning only if:
                            # - effect is not null
                            # - currently stored effect is not the null effect
                            # - currently stored effect is different from incoming effect
                            if value != '' and fx_set[key] != 0 and fx_set[key] != fx_list.index(value):
                                warnings.warn(f'ignoring effect {value} assigned to {key} that already has an assigned effect {fx_list[fx_set[key]]} at m{measure_count}')
                            continue
                        fx_set[key] = fx_list.index(value)
                    # TODO: Check other metadata
                # Note data
                else:
                    adjusted_time = Fraction(noteline_count * current_timesig.upper, subdivision_count * current_timesig.lower)
                    tick_length = Fraction(1 * current_timesig.upper, subdivision_count * current_timesig.lower)
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
                                    fx_index = fx_set.get(input, 0)
                                    note_data_fx[input][holds[input].start] = FXInfo(holds[input].duration, fx_index)
                                    if input in fx_set:
                                        del fx_set[input]
                                del holds[input]
                            elif state == '1':
                                if input.startswith('bt'):
                                    note_data_bt[input][current_time] = BTInfo(0)
                                elif input.startswith('fx'):
                                    note_data_fx[input][current_time] = FXInfo(0, 0)
                                if input in holds.keys():
                                    warnings.warn(f'invalid chip directly after a hold at {current_time}', ParserWarning)
                                    del holds[input]
                            elif state == '2':
                                if input not in holds.keys():
                                    holds[input] = _HoldInfo(current_time)
                                holds[input].duration += tick_length
                        # VOL handled differently
                        elif input.startswith('vol'):
                            # Extend duration
                            if state == '-' and input in last_vol_data:
                                del last_vol_data[input]
                            elif input in last_vol_data:
                                last_vol_data[input].duration += tick_length
                                if last_vol_data[input].duration > Fraction(1, 32):
                                    del last_vol_data[input]

                            # Handle incoming laser
                            if state == '-':
                                is_continued_segment[input] = False
                            elif state == ':':
                                pass
                            else:
                                vol_position = Fraction(LASER_POSITION.index(state), len(LASER_POSITION) - 1)
                                # This handles the case of short laser segment being treated as a slam
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

    for i, fx in enumerate(fx_list):
        print(i, fx)
    return chart
