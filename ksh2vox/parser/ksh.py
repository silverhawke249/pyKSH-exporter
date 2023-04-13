import dataclasses
import itertools
import re
import time
import warnings

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import TextIO, TypedDict

from ..classes import (
    BTInfo,
    ChartInfo,
    DifficultySlot,
    FilterIndex,
    FXInfo,
    ParserWarning,
    SongInfo,
    SPControllerInfo,
    SpinType,
    TiltType,
    TimePoint,
    TimeSignature,
    VolInfo,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
LASER_POSITION = [
    '05AFKPUZejo',
    '0257ACFHKMPSUXZbehjmo',
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno',
]
FX_STATE_MAP = {'0': '0', '1': '2', '2': '1'}
INPUT_BT  = ['bt_a', 'bt_b', 'bt_c', 'bt_d']
INPUT_FX  = ['fx_l', 'fx_r']
INPUT_VOL = ['vol_l', 'vol_r']
FILTER_TYPE_MAP = {
    'peak': FilterIndex.PEAK,
    'lpf1': FilterIndex.LPF,
    'hpf1': FilterIndex.HPF,
    'bitc': FilterIndex.BITCRUSH,
}
NO_EFFECT_INDEX             = 0
KSH_SLAM_DISTANCE           = Fraction(1, 32)
SPIN_CONVERSION_RATE        = Fraction(4, 3) / 48
STOP_CONVERSION_RATE        = Fraction(1, 192)
# KSM provides "top zoom" and "bottom zoom" while SDVX actually offers camera angle
# change and distance change... basically, polar coordinates for the camera. This
# means that the mapping between KSM and SDVX isn't as clean-cut as we'd like.
ZOOM_BOTTOM_CONVERSION_RATE = Decimal(-0.002222)
ZOOM_TOP_CONVERSION_RATE    = Decimal(0.006667)
TILT_CONVERSION_RATE        = Decimal(-0.004200)
LANE_SPLIT_CONVERSION_RATE  = Decimal(0.006667)


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


def convert_laser_pos(s: str) -> Fraction:
    for laser_str in LASER_POSITION:
        if s in laser_str:
            laser_pos = laser_str.index(s)
            return Fraction(laser_pos, len(laser_str) - 1)
    return Fraction()


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

    _fx_list: list[str] = dataclasses.field(default_factory=list, init=False, repr=False)

    # Stateful data for notechart parsing
    _cur_timesig: TimeSignature = dataclasses.field(default=TimeSignature(), init=False, repr=False)
    _cur_filter : FilterIndex   = dataclasses.field(default=FilterIndex.PEAK, init=False, repr=False)

    _filter_changed: bool                    = dataclasses.field(default=False, init=False, repr=False)
    _tilt_segment  : bool                    = dataclasses.field(default=False, init=False, repr=False)
    _recent_vol    : dict[str, _LastVolInfo] = dataclasses.field(default_factory=dict, init=False, repr=False)
    _cont_segment  : dict[str, bool]         = dataclasses.field(init=False, repr=False)
    _wide_segment  : dict[str, bool]         = dataclasses.field(init=False, repr=False)

    _holds : dict[str, _HoldInfo]      = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_fx: dict[str, str]            = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_se: dict[str, int]            = dataclasses.field(default_factory=dict, init=False, repr=False)
    _spins : dict[TimePoint, str]      = dataclasses.field(default_factory=dict, init=False, repr=False)
    _stops : dict[TimePoint, Fraction] = dataclasses.field(default_factory=dict, init=False, repr=False)

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
        self._parse_definitions()
        self._parse_notedata()

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
                self._chart_info.timesigs[TimePoint(1, 0, 1)] = TimeSignature(upper, lower)
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
                if value in FILTER_TYPE_MAP:
                    self._chart_info.active_filter[TimePoint(1, 0, 1)] = FILTER_TYPE_MAP[value]
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

    def _initialize_stateful_data(self) -> None:
        self._cont_segment = {
            'vol_l': False,
            'vol_r': False,
        }
        self._wide_segment = {
            'vol_l': False,
            'vol_r': False,
        }
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

    def _parse_notedata(self) -> None:
        self._initialize_stateful_data()

        # Measure data
        ln_offset   : int       = len(self._raw_metadata) + 1
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
                warnings.warn(f'unrecognized line at line {ln_offset + line_no + 1}: {line}')

        self._chart_info.total_measures = measure_number + 1

        self._handle_notechart_postprocessing()

        # Store note data in chart
        for k, v1 in self._bts.items():
            setattr(self._chart_info.note_data, k, v1)
        for k, v2 in self._fxs.items():
            setattr(self._chart_info.note_data, k, v2)
        for k, v3 in self._vols.items():
            setattr(self._chart_info.note_data, k, v3)

    def _handle_notechart_metadata(self, line: str, cur_time: TimePoint, m_no: int) -> None:
        key, value = line.split('=', 1)
        if key == 't':
            self._chart_info.bpms[cur_time] = Decimal(value)
        elif key == 'beat':
            upper_str, lower_str = value.split('/')
            upper, lower = int(upper_str), int(lower_str)
            # Time signature changes should be at the start of the measure
            # Otherwise, it takes effect on the next measure
            if cur_time.position != 0:
                self._chart_info.timesigs[TimePoint(m_no + 1, 0, 1)] = TimeSignature(upper, lower)
            else:
                self._chart_info.timesigs[TimePoint(m_no, 0, 1)] = TimeSignature(upper, lower)
        elif key == 'stop':
            self._stops[cur_time] = int(value) * STOP_CONVERSION_RATE
        elif key == 'tilt':
            try:
                if value == 'zero':
                    tilt_val = Decimal()
                else:
                    tilt_val = (int(value) * TILT_CONVERSION_RATE).normalize() + 0
                # Modify existing tilt value if it exists
                if cur_time in self._chart_info.spcontroller_data.tilt:
                    self._chart_info.spcontroller_data.tilt[cur_time].end = tilt_val
                else:
                    self._chart_info.spcontroller_data.tilt[cur_time] = SPControllerInfo(
                        tilt_val, tilt_val,
                        is_new_segment=not self._tilt_segment)
                self._tilt_segment = True
            except ValueError:
                if value == 'normal':
                    self._chart_info.tilt_type[cur_time] = TiltType.NORMAL
                    self._tilt_segment = False
                elif value in ['bigger', 'biggest']:
                    self._chart_info.tilt_type[cur_time] = TiltType.BIGGER
                    self._tilt_segment = False
                    if value == 'biggest':
                        warnings.warn(f'downgrading tilt {value} at m{m_no} to "bigger"', ParserWarning)
                elif value in ['keep_normal', 'keep_bigger', 'keep_biggest']:
                    self._chart_info.tilt_type[cur_time] = TiltType.KEEP
                    self._tilt_segment = False
                else:
                    warnings.warn(f'unrecognized tilt mode {value} at m{m_no}', ParserWarning)
        elif key == 'zoom_top':
            zoom_val = (int(value) * ZOOM_TOP_CONVERSION_RATE).normalize() + 0
            if cur_time in self._chart_info.spcontroller_data.zoom_top:
                self._chart_info.spcontroller_data.zoom_top[cur_time].end = zoom_val
            else:
                self._chart_info.spcontroller_data.zoom_top[cur_time] = SPControllerInfo(
                    zoom_val, zoom_val,
                    is_new_segment=False)
        elif key == 'zoom_bottom':
            zoom_val = (int(value) * ZOOM_BOTTOM_CONVERSION_RATE).normalize() + 0
            if cur_time in self._chart_info.spcontroller_data.zoom_bottom:
                self._chart_info.spcontroller_data.zoom_bottom[cur_time].end = zoom_val
            else:
                self._chart_info.spcontroller_data.zoom_bottom[cur_time] = SPControllerInfo(zoom_val, zoom_val,
                is_new_segment=False)
        elif key == 'center_split':
            split_val = (int(value) * LANE_SPLIT_CONVERSION_RATE).normalize() + 0
            if cur_time in self._chart_info.spcontroller_data.lane_split:
                self._chart_info.spcontroller_data.lane_split[cur_time].end = split_val
            else:
                self._chart_info.spcontroller_data.lane_split[cur_time] = SPControllerInfo(split_val, split_val)
        elif key in ['laserrange_l', 'laserrange_r']:
            key = f'vol_{key[-1]}'
            if not self._cont_segment[key]:
                self._wide_segment[key] = True
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
                return
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
            else:
                # TODO: Handle track auto tab
                self._cur_filter = FilterIndex.CUSTOM
            self._chart_info.active_filter[cur_time] = self._cur_filter
        elif ':' in key:
            # TODO: Filter settings
            # > filter:[filter_name]:[parameter]=[value]
            # Technically FX parameters can also be changed here but like no one uses that
            pass
        else:
            # Ignoring all other metadata
            pass

    def _handle_notechart_custom_commands(self, line: str, cur_time: TimePoint) -> None:
        # Remove initial `//`
        line = line[2:]
        if '=' in line:
            # TODO: Define custom commands here
            pass

    def _handle_notechart_notedata(self, line: str, cur_time: TimePoint, subdivision: Fraction) -> None:
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
                    fx_index = NO_EFFECT_INDEX
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
            # Delete "last vol point" if laser segment ends, else extend duration
            if state == '-' and vol in self._recent_vol:
                del self._recent_vol[vol]
            elif vol in self._recent_vol:
                self._recent_vol[vol].duration += subdivision
                # Forget the info if distance is more than a 32nd
                if self._recent_vol[vol].duration > KSH_SLAM_DISTANCE:
                    del self._recent_vol[vol]
            # Handle incoming laser
            if state == '-':
                self._cont_segment[vol] = False
                self._wide_segment[vol] = False
            elif state == ':':
                pass
            else:
                vol_position = convert_laser_pos(state)
                # This handles the case of short laser segment being treated as a slam
                if (vol in self._recent_vol and
                    self._recent_vol[vol].duration <= KSH_SLAM_DISTANCE and
                    self._recent_vol[vol].prev_vol.start != vol_position):
                    last_vol_info = self._recent_vol[vol]
                    self._vols[vol][last_vol_info.when] = VolInfo(
                        last_vol_info.prev_vol.start,
                        vol_position,
                        filter_index=self._cur_filter,
                        is_new_segment=last_vol_info.prev_vol.is_new_segment,
                        wide_laser=last_vol_info.prev_vol.wide_laser)
                else:
                    self._vols[vol][cur_time] = VolInfo(
                        vol_position, vol_position,
                        is_new_segment=not self._cont_segment[vol],
                        wide_laser=self._wide_segment[vol])
                self._recent_vol[vol] = _LastVolInfo(
                    cur_time,
                    Fraction(0),
                    VolInfo(
                        vol_position, vol_position,
                        is_new_segment=not self._cont_segment[vol],
                        wide_laser=self._wide_segment[vol]))
                self._cont_segment[vol] = True
        if spin:
            self._spins[cur_time] = spin

    def _handle_notechart_postprocessing(self) -> None:
        # Equalize FX effects and SE
        for cur_time, fxl_info in self._fxs['fx_l'].items():
            if cur_time not in self._fxs['fx_r']:
                continue
            # Ignore inequal duration
            fxr_info = self._fxs['fx_r'][cur_time]
            if fxl_info.duration != fxr_info.duration:
                continue
            # Copy over effects/SE if and only if one of them is unassigned
            if fxl_info.special == 0 and fxr_info.special != 0:
                fxl_info.special = fxr_info.special
            elif fxl_info.special != 0 and fxr_info.special == 0:
                fxr_info.special = fxl_info.special

        # Apply spins
        # NOTE: Spin duration is given as number of 1/192nds regardless of time signature.
        # spins in KSM persists a little longer -- roughly 1.33x times of its given length.
        # assuming 4/4 time signature, a spin duration of 192 lasts a whole measure (and a
        # bit more), so you multiply this by 4 to get the number of beats the spin will last.
        # ultimately, that means the duration is multiplied by 16/3 and rounded.
        # Spin duration in VOX is given as whole multiples of 1/4th notes.
        for cur_time, state in self._spins.items():
            spin_matched = False
            spin_type, spin_length_str = state[:2], state[2:]
            # Rounding down to avoid spins distracting gameplay
            spin_length = int(Fraction(spin_length_str) * SPIN_CONVERSION_RATE)
            for vol_data in self._vols.values():
                if cur_time not in vol_data:
                    continue
                vol_info = vol_data[cur_time]
                if vol_info.start < vol_info.end:
                    if spin_type[1] == ')':
                        vol_info.spin_type = SpinType.SINGLE_SPIN
                        vol_info.spin_duration = spin_length
                        spin_matched = True
                    # Converting swing effect to half-spin
                    elif spin_type[1] == '>':
                        vol_info.spin_type = SpinType.HALF_SPIN
                        vol_info.spin_duration = spin_length
                        spin_matched = True
                elif vol_info.start > vol_info.end:
                    if spin_type[1] == '(':
                        vol_info.spin_type = SpinType.SINGLE_SPIN
                        vol_info.spin_duration = spin_length
                        spin_matched = True
                    # Converting swing effect to half-spin
                    elif spin_type[1] == '<':
                        vol_info.spin_type = SpinType.HALF_SPIN
                        vol_info.spin_duration = spin_length
                        spin_matched = True
                if spin_matched:
                    break
            if not spin_matched:
                warnings.warn(f'cannot match spin {state} at {cur_time} with any slam', ParserWarning)

        # TODO: Convert stop durations to timepoints
        for cur_time, duration in self._stops.items():
            pass

        # Mark laser points as end of segment
        for vol_data in self._vols.values():
            if not vol_data:
                continue
            time_list = list(vol_data.keys())
            for cur_time, next_time in itertools.pairwise(time_list):
                if vol_data[next_time].is_new_segment:
                    vol_data[cur_time].last_of_segment = True
            vol_data[next_time].last_of_segment = True

        # TODO: Convert detected FX list into effect instances

        # TODO: Insert laser midpoints where filter type changes

    def _parse_measure(self, measure: list[str], m_no: int, m_linecount: int) -> None:
        # Check time signatures that get pushed to the next measure
        if TimePoint(m_no, 0, 1) in self._chart_info.timesigs:
            self._cur_timesig = self._chart_info.timesigs[TimePoint(m_no, 0, 1)]

        noteline_count = 0
        for line in measure:
            subdivision = Fraction(1 * self._cur_timesig.upper, m_linecount * self._cur_timesig.lower)
            cur_subdiv  = noteline_count * subdivision
            cur_time    = TimePoint(m_no, cur_subdiv.numerator, cur_subdiv.denominator)

            # 1. Metadata
            if '=' in line:
                self._handle_notechart_metadata(line, cur_time, m_no)
            # 2. Comment
            elif line.startswith('//'):
                self._handle_notechart_custom_commands(line, cur_time)
            # 3. Notedata
            else:
                self._handle_notechart_notedata(line, cur_time, subdivision)
                noteline_count += 1

    def _parse_definitions(self) -> None:
        # TODO: This
        ln_offset: int = len(self._raw_metadata) + len(self._raw_notedata) + 1
        for line_no, line in enumerate(self._raw_definitions):
            if not line.startswith('#'):
                warnings.warn(f'unrecognized line at line {ln_offset + line_no + 1}: {line}', ParserWarning)
            line_type, name, definition = line[1:].split(' ')
            if line_type == 'define_fx':
                print(f'{name}: {definition}')
            elif line_type == 'define_filter':
                print(f'{name}: {definition}')
            else:
                warnings.warn(f'unrecognized definition at line {ln_offset + line_no + 1}: {definition}', ParserWarning)

    def _get_distance(self, a: TimePoint, b: TimePoint) -> Fraction:
        """ Calculate the distance between two timepoints as a fraction. """
        if a == b:
            return Fraction()
        if b < a:
            a, b = b, a

        distance = Fraction()
        for m_no in range(a.measure, b.measure):
            distance += self._chart_info.get_timesig(m_no).as_fraction()
        distance += b.position - a.position

        return distance

    def _add_duration(self, a: TimePoint, b: Fraction) -> TimePoint:
        """ Calculate the resulting timepoint after adding an amount of time to a timepoint. """
        modified_length = a.position + b

        m_no = a.measure
        while modified_length >= (m_len := self._chart_info.get_timesig(m_no).as_fraction()):
            modified_length -= m_len
            m_no += 1

        return TimePoint(m_no, modified_length.numerator, modified_length.denominator)

    def write_xml(self, f: TextIO):
        f.write(f'  <music id="{self._song_info.id}">\n'
                 '    <info>\n'
                f'      <label>{self._song_info.id}</label>\n'
                f'      <title_name>{self._song_info.title}</title_name>\n'
                f'      <title_yomigana>{self._song_info.title_yomigana}</title_yomigana>\n'
                f'      <artist_name>{self._song_info.artist}</artist_name>\n'
                f'      <artist_yomigana>{self._song_info.artist_yomigana}</artist_yomigana>\n'
                f'      <ascii>{self._song_info.ascii_label}</ascii>\n'
                f'      <bpm_max __type="u32">{self._song_info.max_bpm * 100:.0f}</bpm_max>\n'
                f'      <bpm_min __type="u32">{self._song_info.min_bpm * 100:.0f}</bpm_min>\n'
                f'      <distribution_date __type="u32">{self._song_info.release_date}</distribution_date>\n'
                f'      <volume __type="u16">{self._song_info.music_volume}</volume>\n'
                f'      <bg_no __type="u16">{self._song_info.background.value}</bg_no>\n'
                 '      <genre __type="u8">32</genre>\n'
                 '      <is_fixed __type="u8">1</is_fixed>\n'
                 '      <version __type="u8">4</version>\n'
                 '      <demo_pri __type="s8">-2</demo_pri>\n'
                f'      <inf_ver __type="u8">{self._song_info.inf_ver.value}</inf_ver>\n'
                 '    </info>\n'
                 '    <difficulty>\n')

        for diff in DifficultySlot:
            f.write(f'      <{diff.name.lower()}>\n')
            if self._chart_info.difficulty == diff:
                f.write(f'        <difnum __type="u8">{self._chart_info.level}</difnum>\n'
                        f'        <illustrator>{self._chart_info.illustrator}</illustrator>\n'
                        f'        <effected_by>{self._chart_info.effector}</effected_by>\n')
            else:
                f.write('        <difnum __type="u8">0</difnum>\n'
                        '        <illustrator>dummy</illustrator>\n'
                        '        <effected_by>dummy</effected_by>\n')
            f.write('        <price __type="s32">-1</price>\n'
                    '        <limited __type="u8">3</limited>\n'
                   f'      </{diff.name.lower()}>\n')

    def write_vol(self, f: TextIO, notedata: dict[TimePoint, VolInfo], apply_ease: bool):
        # TODO: Handle easing
        for timept, vol in notedata.items():
            # Not slam
            if vol.start == vol.end:
                pass
            # Slam
            else:
                pass
            segment_indicator = 1 if vol.is_new_segment else 2 if vol.last_of_segment else 0
            filter_type = 0
            wide_indicator = 2 if vol.wide_laser else 1
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{float(vol.start):.6f}\t'
                    f'{segment_indicator}\t{vol.spin_type.value}\t{filter_type}\t{wide_indicator}\t'
                    f'0\t{vol.ease_type.value}\t{vol.spin_duration}\n')
            if vol.start != vol.end:
                f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{float(vol.end):.6f}\t'
                        f'{segment_indicator}\t{vol.spin_type.value}\t{filter_type}\t'
                        f'{wide_indicator}\t0\t{vol.ease_type.value}\t{vol.spin_duration}\n')

    def write_fx(self, f: TextIO, notedata: dict[TimePoint, FXInfo]):
        for timept, fx in notedata.items():
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{fx.duration_as_tick()}\t{fx.special}\n')

    def write_bt(self, f: TextIO, notedata: dict[TimePoint, BTInfo]):
        for timept, bt in notedata.items():
            # What even is the last number for in BT holds?
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{bt.duration_as_tick()}\t0\n')

    def write_vox(self, f: TextIO):
        # Header
        f.write('//====================================\n'
                '// SOUND VOLTEX OUTPUT TEXT FILE\n'
               f'// Converted from {self._ksh_path.name}\n'
               f'// at {time.strftime("%Y.%m.%d %H:%M:%S")}\n'
                '//====================================\n'
                '\n')

        # VOX version
        f.write('#FORMAT VERSION\n'
                '12\n'
                '#END\n'
                '\n')

        # Time signatures
        f.write('#BEAT INFO\n')
        for timept, timesig in self._chart_info.timesigs.items():
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{timesig.upper}\t{timesig.lower}\n')
        f.write('#END\n')
        f.write('\n')

        # BPMs
        f.write('#BPM INFO\n')
        timepoint_set = set(self._chart_info.bpms.keys())
        timepoint_set.update(self._chart_info.stops.keys())
        for timept in sorted(timepoint_set):
            pass
        f.write('#END\n')
        f.write('\n')

        # Tilt modes
        f.write('#TILT MODE INFO\n')
        for timept, tilt_type in self._chart_info.tilt_type.items():
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{tilt_type.value}\n')
        f.write('#END\n')
        f.write('\n')

        # Lyric info (?)
        f.write('#LYRIC INFO\n'
                '#END\n'
                '\n')

        # End position
        f.write('#END POSITION\n'
               f'{self._chart_info.total_measures:03},01,00\n'
                '#END\n')
        f.write('\n')

        # Filter parameters
        f.write('#TAB EFFECT INFO\n')
        for filter in self._chart_info.filter_list:
            f.write(filter.to_vox_string())
            f.write('\n')
        f.write('#END\n')
        f.write('\n')

        # FX parameters
        f.write('#FXBUTTON EFFECT INFO\n')
        for effect in self._chart_info.effect_list:
            f.write(effect.to_vox_string())
            f.write('\n')
        f.write('#END\n')
        f.write('\n')

        # TODO: Tab parameters (FX on lasers parameters)
        f.write('#TAB PARAM ASSIGN INFO\n')
        for autotab in self._chart_info.autotab_list:
            f.write(autotab.to_vox_string())
        f.write('#END\n')
        f.write('\n')

        # Reverb effect param (?)
        f.write('#REVERB EFFECT PARAM\n'
                '#END\n'
                '\n')

        # == TRACK INFO ==
        f.write('//====================================\n'
                '// TRACK INFO\n'
                '//====================================\n'
                '\n')

        # Note data (TRACK1~8)
        f.write('#TRACK1\n')
        self.write_vol(f, self._chart_info.note_data.vol_l, apply_ease=True)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK2\n')
        self.write_fx(f, self._chart_info.note_data.fx_l)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK3\n')
        self.write_bt(f, self._chart_info.note_data.bt_a)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK4\n')
        self.write_bt(f, self._chart_info.note_data.bt_b)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK5\n')
        self.write_bt(f, self._chart_info.note_data.bt_c)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK6\n')
        self.write_bt(f, self._chart_info.note_data.bt_d)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK7\n')
        self.write_fx(f, self._chart_info.note_data.fx_r)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK8\n')
        self.write_vol(f, self._chart_info.note_data.vol_r, apply_ease=True)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        # TODO: Track auto tab (FX on lasers activation)
        f.write('#TRACK AUTO TAB\n')
        for timept, autotab_info in self._chart_info.autotab_infos.items():
            pass
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        # Original TRACK1/8
        f.write('#TRACK ORIGINAL L\n')
        self.write_vol(f, self._chart_info.note_data.vol_l, apply_ease=False)
        f.write('#END\n')
        f.write('\n')

        f.write('#TRACK ORIGINAL R\n')
        self.write_vol(f, self._chart_info.note_data.vol_r, apply_ease=False)
        f.write('#END\n')
        f.write('\n')

        # == SPCONTROLER INFO == (sic)
        f.write('//====================================\n'
                '// SPCONTROLER INFO\n'
                '//====================================\n'
                '\n')

        # SPController data
        f.write('#SPCONTROLER\n')
        f.write('001,01,00\tRealize	3\t0\t36.12\t60.12\t110.12\t0.00\n'
                '001,01,00\tRealize	4\t0\t0.62\t0.72\t1.03\t0.00\n'
                '001,01,00\tAIRL_ScaX\t1\t0\t0.00\t1.00\t0.00\t0.00\n'
                '001,01,00\tAIRR_ScaX\t1\t0\t0.00\t2.00\t0.00\t0.00\n')
        for timept, zt in self._chart_info.spcontroller_data.zoom_top.items():
            pass
        for timept, zb in self._chart_info.spcontroller_data.zoom_bottom.items():
            pass
        for timept, tilt in self._chart_info.spcontroller_data.tilt.items():
            pass
        for timept, ls in self._chart_info.spcontroller_data.lane_split.items():
            pass
        for timept, lt in self._chart_info.spcontroller_data.lane_toggle.items():
            pass
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')
