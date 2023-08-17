import dataclasses
import itertools
import logging
import re
import time

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import TextIO
from xml.sax.saxutils import escape

from ..classes import (
    effects,
    filters,
)
from ..classes.base import (
    AutoTabInfo,
    ParserWarning,
    TimePoint,
    TimeSignature,
)
from ..classes.chart import (
    BTInfo,
    ChartInfo,
    FXInfo,
    SPControllerInfo,
    VolInfo,
)
from ..classes.enums import (
    DifficultySlot,
    EasingType,
    FilterIndex,
    SegmentFlag,
    SpinType,
    TiltType,
)
from ..classes.song import (
    SongInfo,
)
from ..utils import (
    clamp,
    interpolate,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
TITLE_REGEX = re.compile(r'[^a-zA-Z0-9]+')
LASER_POSITION = [
    '05AFKPUZejo',
    '0257ACFHKMPSUXZbehjmo',
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno',
]
INPUT_BT  = ['bt_a', 'bt_b', 'bt_c', 'bt_d']
INPUT_FX  = ['fx_l', 'fx_r']
INPUT_VOL = ['vol_l', 'vol_r']
FILTER_TYPE_MAP = {
    'peak': FilterIndex.PEAK,
    'lpf1': FilterIndex.LPF,
    'hpf1': FilterIndex.HPF,
    'bitc': FilterIndex.BITCRUSH,
}
KSH_EFFECT_MAP: dict[str, effects.Effect] = {
    'Retrigger' : effects.Retrigger(),
    'Gate'      : effects.Gate(),
    'Flanger'   : effects.Flanger(),
    'PitchShift': effects.PitchShift(),
    'BitCrusher': effects.Bitcrush(),
    'Phaser'    : effects.Flanger(mix=50, period=2, feedback=0.35, stereo_width=0, hicut_gain=8),
    'Wobble'    : effects.Wobble(),
    'TapeStop'  : effects.Tapestop(),
    'Echo'      : effects.RetriggerEx(mix=100, wavelength=4, update_period=4, feedback=0.6, amount=1, decay=0.8),
    'SideChain' : effects.Sidechain(),
}
NO_EFFECT_INDEX             = 0
KSH_SLAM_DISTANCE           = Fraction(1, 32)
INTERPOLATION_DISTANCE      = Fraction(1, 64)
SPIN_CONVERSION_RATE        = Fraction(4, 3) / 48
STOP_CONVERSION_RATE        = Fraction(1, 192)
# KSM provides "top zoom" and "bottom zoom" while SDVX actually offers camera angle
# change and distance change... basically, polar coordinates for the camera. This
# means that the mapping between KSM and SDVX isn't as clean-cut as we'd like.
ZOOM_BOTTOM_CONVERSION_RATE = Decimal('-0.006667')
ZOOM_TOP_CONVERSION_RATE    = Decimal('0.002222')
TILT_CONVERSION_RATE        = Decimal('-0.420000')
LANE_SPLIT_CONVERSION_RATE  = Decimal('0.006667')

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _HoldInfo:
    start: TimePoint
    duration: Fraction = Fraction(0)


@dataclasses.dataclass
class _LastVolInfo:
    when: TimePoint
    duration: Fraction
    prev_vol: VolInfo


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
    _cur_timesig: TimeSignature         = dataclasses.field(default=TimeSignature(), init=False, repr=False)
    _cur_filter : FilterIndex           = dataclasses.field(default=FilterIndex.PEAK, init=False, repr=False)
    # When a key is missing from this dict, it means that easing is currently active on that volume track
    _cur_easing : dict[str, EasingType] = dataclasses.field(default_factory=dict, init=False, repr=False)

    _filter_changed : bool                    = dataclasses.field(default=False, init=False, repr=False)
    _tilt_segment   : bool                    = dataclasses.field(default=False, init=False, repr=False)
    _last_tilt_value: Decimal                 = dataclasses.field(default_factory=Decimal, init=False, repr=False)
    _filter_override: FilterIndex             = dataclasses.field(default=FilterIndex.PEAK, init=False, repr=False)
    _recent_vol     : dict[str, _LastVolInfo] = dataclasses.field(default_factory=dict, init=False, repr=False)
    _cont_segment   : dict[str, bool]         = dataclasses.field(init=False, repr=False)
    _wide_segment   : dict[str, bool]         = dataclasses.field(init=False, repr=False)

    _holds : dict[str, _HoldInfo]      = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_fx: dict[str, str]            = dataclasses.field(default_factory=dict, init=False, repr=False)
    _set_se: dict[str, int]            = dataclasses.field(default_factory=dict, init=False, repr=False)
    _spins : dict[TimePoint, str]      = dataclasses.field(default_factory=dict, init=False, repr=False)
    _stops : dict[TimePoint, Fraction] = dataclasses.field(default_factory=dict, init=False, repr=False)

    _ease_start    : dict[str, TimePoint]                          = dataclasses.field(default_factory=dict, init=False, repr=False)
    _ease_ranges   : dict[TimePoint, tuple[float, float]]          = dataclasses.field(default_factory=dict, init=False, repr=False)
    _ease_midpoints: dict[str, list[tuple[TimePoint, EasingType]]] = dataclasses.field(default_factory=dict, init=False, repr=False)

    _filter_names    : dict[TimePoint, str] = dataclasses.field(default_factory=dict, init=False, repr=False)
    _filter_to_effect: dict[str, int]       = dataclasses.field(default_factory=dict, init=False, repr=False)

    _bts : dict[str, dict[TimePoint, BTInfo]]  = dataclasses.field(init=False, repr=False)
    _fxs : dict[str, dict[TimePoint, FXInfo]]  = dataclasses.field(init=False, repr=False)
    _vols: dict[str, dict[TimePoint, VolInfo]] = dataclasses.field(init=False, repr=False)

    _final_zoom_top_timepoint   : TimePoint = dataclasses.field(init=False, repr=False)
    _final_zoom_bottom_timepoint: TimePoint = dataclasses.field(init=False, repr=False)
    _first_lane_split_timepoint : TimePoint | None = dataclasses.field(default=None, init=False, repr=False)
    _final_lane_split_timepoint : TimePoint | None = dataclasses.field(default=None, init=False, repr=False)

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
            try:
                if '=' not in line:
                    logger.warning(f'unrecognized line at line {line_no + 1}: "{line}"')
                key, value = line.split('=', 1)
                if key == 'title':
                    self._song_info.title = value
                    self._song_info.ascii_label = ''.join(TITLE_REGEX.split(value)).lower()
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
                        self._chart_info.bpms[TimePoint()] = bpm
                elif key == 'beat':
                    upper_str, lower_str = value.split('/')
                    upper, lower = int(upper_str), int(lower_str)
                    self._chart_info.timesigs[TimePoint()] = TimeSignature(upper, lower)
                    self._cur_timesig = TimeSignature(upper, lower)
                elif key == 'm':
                    self._chart_info.music_path, *music_path_ex = value.split(';')
                    if music_path_ex:
                        logger.warning('multiple song files are not supported yet')
                elif key == 'mvol':
                    self._song_info.music_volume = int(value)
                elif key == 'o':
                    self._chart_info.music_offset = int(value)
                elif key == 'po':
                    self._chart_info.preview_start = int(value)
                elif key == 'filtertype':
                    if value in FILTER_TYPE_MAP:
                        self._chart_info.active_filter[TimePoint()] = FILTER_TYPE_MAP[value]
                elif key == 'ver':
                    # You know, I should probably differentiate handling top/bottom zooms depending if
                    # the version is >= 167 or not, but I'm most likely not going to fucking bother
                    try:
                        version = int(value)
                        if version < 160:
                            raise NotImplementedError(f'ksh file version too old (got {value})')
                    except ValueError as e:
                        raise NotImplementedError(f'ksh file version too old (got {value})') from e
                else:
                    # Silently ignoring all other metadata
                    pass
            except ValueError as e:
                logger.warning(str(e))

    def _initialize_stateful_data(self) -> None:
        self._ease_midpoints = {
            'vol_l': [],
            'vol_r': [],
        }
        self._cur_easing = {
            'vol_l': EasingType.NO_EASING,
            'vol_r': EasingType.NO_EASING,
        }
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
        self._final_zoom_bottom_timepoint = TimePoint()
        self._final_zoom_top_timepoint = TimePoint()

    def _parse_notedata(self) -> None:
        self._initialize_stateful_data()

        # Measure data
        ln_offset        : int       = len(self._raw_metadata) + 1
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
                logger.warning(f'unrecognized line at line {ln_offset + line_no + 1}: "{line}"')

        self._handle_notechart_postprocessing()

        # Store note data in chart
        for k, v1 in self._bts.items():
            v1 = dict(sorted(v1.items()))
            setattr(self._chart_info.note_data, k, v1)
        for k, v2 in self._fxs.items():
            v2 = dict(sorted(v2.items()))
            setattr(self._chart_info.note_data, k, v2)
        for k, v3 in self._vols.items():
            v3 = dict(sorted(v3.items()))
            setattr(self._chart_info.note_data, k, v3)

        final_note_timept = TimePoint()
        for _, timept, note_data in self._chart_info.note_data.iter_notes():
            if not isinstance(note_data, VolInfo) and note_data.duration != 0:
                timept = self._chart_info.add_duration(timept, note_data.duration)
            final_note_timept = max(timept, final_note_timept)

        # TODO: See if rounding up to next measure is necessary or not
        self._chart_info.end_measure = final_note_timept.measure + 2

    def _handle_notechart_metadata(self, line: str, cur_time: TimePoint, m_no: int) -> None:
        key, value = line.split('=', 1)
        try:
            if key == 't':
                self._chart_info.bpms[cur_time] = Decimal(value)
            elif key == 'beat':
                if '/' not in value:
                    logger.warning(f'invalid time signature (got {value})')
                upper_str, lower_str = value.split('/')
                upper, lower = int(upper_str), int(lower_str)
                # Time signature changes should be at the start of the measure
                # Otherwise, it takes effect on the next measure
                if cur_time.position != 0:
                    self._chart_info.timesigs[TimePoint(m_no + 1, 0, 1)] = TimeSignature(upper, lower)
                else:
                    self._chart_info.timesigs[TimePoint(m_no, 0, 1)] = TimeSignature(upper, lower)
                    self._cur_timesig = TimeSignature(upper, lower)
            elif key == 'stop':
                self._stops[cur_time] = int(value) * STOP_CONVERSION_RATE
            elif key == 'tilt':
                try:
                    if value == 'zero':
                        tilt_val = Decimal()
                    else:
                        tilt_val = (Decimal(value) * TILT_CONVERSION_RATE).normalize() + 0
                    self._last_tilt_value = tilt_val
                    # Modify existing tilt value if it exists
                    if cur_time in self._chart_info.spcontroller_data.tilt:
                        self._chart_info.spcontroller_data.tilt[cur_time].end = tilt_val
                    else:
                        self._chart_info.spcontroller_data.tilt[cur_time] = SPControllerInfo(
                            tilt_val, tilt_val,
                            point_type=SegmentFlag.MIDDLE if self._tilt_segment else SegmentFlag.START)
                    self._tilt_segment = True
                except InvalidOperation:
                    if value not in ['normal', 'bigger', 'biggest', 'keep_normal', 'keep_bigger', 'keep_biggest']:
                        logger.warning(f'unrecognized tilt mode "{value}" at m{m_no}')
                    else:
                        # Make sure manual tilt segments are terminated properly
                        if self._tilt_segment and cur_time not in self._chart_info.spcontroller_data.tilt:
                            self._chart_info.spcontroller_data.tilt[cur_time] = SPControllerInfo(
                                self._last_tilt_value, self._last_tilt_value,
                                point_type=SegmentFlag.MIDDLE)  # Will get updated later anyway
                        self._tilt_segment = False
                        if value == 'normal':
                            self._chart_info.tilt_type[cur_time] = TiltType.NORMAL
                        elif value in ['bigger', 'biggest']:
                            self._chart_info.tilt_type[cur_time] = TiltType.BIGGER
                            if value == 'biggest':
                                logger.warning(f'downgrading tilt "{value}" at m{m_no} to "bigger"')
                        elif value in ['keep_normal', 'keep_bigger', 'keep_biggest']:
                            self._chart_info.tilt_type[cur_time] = TiltType.KEEP
            elif key == 'zoom_top':
                zoom_val = (int(value) * ZOOM_TOP_CONVERSION_RATE).normalize() + 0
                if cur_time in self._chart_info.spcontroller_data.zoom_top:
                    self._chart_info.spcontroller_data.zoom_top[cur_time].end = zoom_val
                else:
                    self._chart_info.spcontroller_data.zoom_top[cur_time] = SPControllerInfo(
                        zoom_val, zoom_val,
                        point_type=SegmentFlag.MIDDLE)
                self._final_zoom_top_timepoint = cur_time
            elif key == 'zoom_bottom':
                zoom_val = (int(value) * ZOOM_BOTTOM_CONVERSION_RATE).normalize() + 0
                if cur_time in self._chart_info.spcontroller_data.zoom_bottom:
                    self._chart_info.spcontroller_data.zoom_bottom[cur_time].end = zoom_val
                else:
                    self._chart_info.spcontroller_data.zoom_bottom[cur_time] = SPControllerInfo(
                        zoom_val, zoom_val,
                        point_type=SegmentFlag.MIDDLE)
                self._final_zoom_bottom_timepoint = cur_time
            elif key == 'center_split':
                if self._first_lane_split_timepoint is None:
                    self._first_lane_split_timepoint = cur_time
                self._final_lane_split_timepoint = cur_time
                split_val = (int(value) * LANE_SPLIT_CONVERSION_RATE).normalize() + 0
                if cur_time in self._chart_info.spcontroller_data.lane_split:
                    self._chart_info.spcontroller_data.lane_split[cur_time].end = split_val
                else:
                    self._chart_info.spcontroller_data.lane_split[cur_time] = SPControllerInfo(
                        split_val, split_val,
                        point_type=SegmentFlag.MIDDLE)
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
                        logger.warning(f'ignoring effect "{value}" assigned to {key} that already has an assigned '
                                        f'effect "{self._set_fx[key]}" at m{m_no}', ParserWarning)
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
                filter_now: FilterIndex
                self._filter_names[cur_time] = value
                if self._filter_override != FilterIndex.PEAK:
                    filter_now = self._filter_override
                    self._filter_override = FilterIndex.PEAK
                elif value in FILTER_TYPE_MAP:
                    filter_now = FILTER_TYPE_MAP[value]
                else:
                    filter_now = FilterIndex.CUSTOM
                if filter_now != self._cur_filter:
                    self._cur_filter = filter_now
                    self._chart_info.active_filter[cur_time] = filter_now
            elif ':' in key:
                # This might get supported in the future, but is too complicated
                pass
            else:
                # Silently ignoring all other metadata
                pass
        except ValueError as e:
            logger.warning(str(e))

    def _handle_notechart_custom_commands(self, line: str, cur_time: TimePoint) -> None:
        # Remove initial `//`
        line = line[2:]
        for chunk in line.split(';'):
            if '=' in chunk:
                name, value = chunk.split('=', 1)
            else:
                name = chunk
                value = ''
            # FX SE
            if name == 'lightFXL':
                self._set_se['fx_l'] = int(value)
            elif name == 'lightFXR':
                self._set_se['fx_r'] = int(value)
            elif name == 'lightFXLR':
                self._set_se['fx_l'] = int(value)
                self._set_se['fx_r'] = int(value)
            # Curves/easing
            elif name == 'curveBeginL':
                self._ease_start['vol_l'] = cur_time
                self._cur_easing['vol_l'] = EasingType(int(value))
            elif name == 'curveBeginR':
                self._ease_start['vol_r'] = cur_time
                self._cur_easing['vol_r'] = EasingType(int(value))
            elif name == 'curveBeginLR':
                self._ease_start['vol_l'] = cur_time
                if ',' in value:
                    value_l, value_r = value.split(',')[:2]
                else:
                    value_l, value_r = value, value
                self._ease_start['vol_l'] = cur_time
                self._cur_easing['vol_l'] = EasingType(int(value_l))
                self._ease_start['vol_r'] = cur_time
                self._cur_easing['vol_r'] = EasingType(int(value_r))
            elif name == 'curveBeginSpL':
                values = value.split(',')
                if len(values) != 3:
                    raise ValueError('incorrect number of args supplied to curveBeginSpL')
                ease, init_str, final_str = value.split(',')
                init, final = float(init_str), float(final_str)
                if init > final:
                    init, final = final, init
                init = clamp(init, 0.0, 1.0)
                final = clamp(final, 0.0, 1.0)
                self._ease_start['vol_l'] = cur_time
                self._cur_easing['vol_l'] = EasingType(int(ease))
                self._ease_ranges[cur_time] = init, final
            elif name == 'curveBeginSpR':
                values = value.split(',')
                if len(values) != 3:
                    raise ValueError('incorrect number of args supplied to curveBeginSpR')
                ease, init_str, final_str = value.split(',')
                init, final = float(init_str), float(final_str)
                if init > final:
                    init, final = final, init
                init = clamp(init, 0.0, 1.0)
                final = clamp(final, 0.0, 1.0)
                self._ease_start['vol_r'] = cur_time
                self._cur_easing['vol_r'] = EasingType(int(ease))
                self._ease_ranges[cur_time] = init, final
            elif name == 'curveEndL':
                self._ease_start['vol_l'] = cur_time
                self._cur_easing['vol_l'] = EasingType.NO_EASING
            elif name == 'curveEndR':
                self._ease_start['vol_r'] = cur_time
                self._cur_easing['vol_r'] = EasingType.NO_EASING
            elif name == 'curveEndLR':
                self._ease_start['vol_l'] = cur_time
                self._cur_easing['vol_l'] = EasingType.NO_EASING
                self._ease_start['vol_r'] = cur_time
                self._cur_easing['vol_r'] = EasingType.NO_EASING
            elif name == 'applyFilter':
                if value == 'lpf':
                    filter_now = FilterIndex.LPF
                elif value == 'hpf':
                    filter_now = FilterIndex.HPF
                elif value == 'bitc':
                    filter_now = FilterIndex.BITCRUSH
                else:
                    intval = int(value)
                    filter_now = FilterIndex(intval if 1 <= intval <= 5 else 0)
                if filter_now == FilterIndex.PEAK:
                    return
                self._filter_override = filter_now
                self._cur_filter = filter_now
                if cur_time in self._chart_info.active_filter:
                    self._chart_info.active_filter[cur_time] = filter_now
            else:
                # Silently ignoring all other metadata
                pass

    def _handle_notechart_notedata(self, line: str, cur_time: TimePoint, subdivision: Fraction) -> None:
        bts, fxs, vols_and_spin = line.split('|')
        vols = vols_and_spin[:2]
        spin = vols_and_spin[2:]
        # BTs
        for bt, state in zip(INPUT_BT, bts):
            if state == '0' and bt in self._holds:
                self._bts[bt][self._holds[bt].start] = BTInfo(self._holds[bt].duration)
                del self._holds[bt]
            if state == '1':
                if bt in self._holds:
                    logger.warning(f'improperly terminated hold at {cur_time}')
                    del self._holds[bt]
                self._bts[bt][cur_time] = BTInfo(0)
            if state == '2':
                if bt not in self._holds:
                    self._holds[bt] = _HoldInfo(cur_time)
                self._holds[bt].duration += subdivision
        # FXs
        for fx, state in zip(INPUT_FX, fxs):
            if state == '0' and fx in self._holds:
                fx_effect = self._set_fx.get(fx, None)
                if fx in self._set_fx:
                    del self._set_fx[fx]
                if not fx_effect:
                    fx_index = NO_EFFECT_INDEX
                else:
                    fx_index = self._fx_list.index(fx_effect)
                self._fxs[fx][self._holds[fx].start] = FXInfo(self._holds[fx].duration, fx_index)
                del self._holds[fx]
            if state == '1':
                if fx not in self._holds:
                    self._holds[fx] = _HoldInfo(cur_time)
                self._holds[fx].duration += subdivision
            if state == '2':
                if fx in self._holds:
                    logger.warning(f'improperly terminated hold at {cur_time}')
                    del self._holds[fx]
                se_index = self._set_se.get(fx, 0)
                self._fxs[fx][cur_time] = FXInfo(0, se_index)
            # Clean up -- FX SE only affects the FX chip immediately after
            if fx in self._set_se:
                del self._set_se[fx]
        # VOLs
        for vol, state in zip(INPUT_VOL, vols):
            # Handle incoming laser
            if state == '-':
                self._cont_segment[vol] = False
                self._wide_segment[vol] = False
                if vol in self._recent_vol:
                    del self._recent_vol[vol]
                # Warn if curve special command is issued outside of laser segments
                if vol in self._cur_easing and self._cur_easing[vol] != EasingType.NO_EASING:
                    self._cur_easing[vol] = EasingType.NO_EASING
                    logger.warning(f'curve command for {vol} exists outside of laser segment at {cur_time}')
                # Warn if curve special command extends beyond current laser segment
                elif vol not in self._cur_easing:
                    self._cur_easing[vol] = EasingType.NO_EASING
                    logger.error(f'curve command not closed after {vol} segment at {cur_time}')
            elif state == ':':
                # Add (linearly) interpolated laser point when curve command does not coincide with a laser point
                # This obsoletes the warning that was implemented below
                if vol in self._cur_easing and cur_time == self._ease_start[vol]:
                    self._ease_midpoints[vol].append((cur_time, self._cur_easing[vol]))
                    del self._cur_easing[vol]
            else:
                vol_position = convert_laser_pos(state)
                # This handles the case of short laser segment being treated as a slam
                if (vol in self._recent_vol and
                    self._recent_vol[vol].duration <= KSH_SLAM_DISTANCE and
                    self._recent_vol[vol].prev_vol.start != vol_position):
                    last_vol_info = self._recent_vol[vol]
                    logger.debug(f'{vol}: slam at {last_vol_info.when}, distance={last_vol_info.duration}')
                    self._vols[vol][last_vol_info.when] = VolInfo(
                        last_vol_info.prev_vol.start, vol_position,
                        ease_type=last_vol_info.prev_vol.ease_type,
                        filter_index=self._cur_filter,
                        point_type=last_vol_info.prev_vol.point_type,
                        wide_laser=last_vol_info.prev_vol.wide_laser)
                else:
                    # Ignoring midpoints while doing easing...
                    # This is done here to avoid breaking slams
                    if vol in self._cur_easing:
                        self._vols[vol][cur_time] = VolInfo(
                            vol_position, vol_position,
                            ease_type=self._cur_easing[vol],
                            filter_index=self._cur_filter,
                            point_type=SegmentFlag.MIDDLE if self._cont_segment[vol] else SegmentFlag.START,
                            wide_laser=self._wide_segment[vol])
                if vol in self._cur_easing:
                    self._recent_vol[vol] = _LastVolInfo(
                        cur_time,
                        Fraction(0),
                        VolInfo(
                            vol_position, vol_position,
                            ease_type=self._cur_easing[vol],
                            filter_index=self._cur_filter,
                            point_type=SegmentFlag.MIDDLE if self._cont_segment[vol] else SegmentFlag.START,
                            wide_laser=self._wide_segment[vol]))
                    self._cont_segment[vol] = True
                    if self._cur_easing[vol] != EasingType.NO_EASING:
                        del self._cur_easing[vol]
            # Delete "last vol point" if laser segment ends, else extend duration
            if vol in self._recent_vol:
                self._recent_vol[vol].duration += subdivision
                # Forget the info if distance is more than a 32nd
                if self._recent_vol[vol].duration > KSH_SLAM_DISTANCE:
                    del self._recent_vol[vol]
        if spin:
            self._spins[cur_time] = spin

    def _handle_notechart_postprocessing(self) -> None:
        # Equalize FX effects and SE
        for cur_time, fxl_info in self._fxs['fx_l'].items():
            if cur_time not in self._fxs['fx_r']:
                continue
            # Don't copy if durations aren't equal
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
            # Rounding to closest integer for accuracy, but avoid zero length
            spin_length = round(Fraction(spin_length_str) * SPIN_CONVERSION_RATE)
            if spin_length == 0:
                spin_length = 1
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
                logger.warning(f'cannot match spin "{state}" at {cur_time} with any slam')

        # Convert stop durations to timepoints
        for cur_time, duration in self._stops.items():
            self._chart_info.stops[cur_time] = True
            stop_end = self._chart_info.add_duration(cur_time, duration)
            self._chart_info.stops[stop_end] = False

        # Insert points where easing change happens without a laser point
        new_ease_points: dict[str, list[tuple[TimePoint, VolInfo]]] = {
            'vol_l': [],
            'vol_r': [],
        }
        for vol_name, ease_data in self._ease_midpoints.items():
            vol_data = self._vols[vol_name]
            for timept, easing_type in ease_data:
                # Get timepoints for laser points exactly before and after the ease timepoint
                time_i = TimePoint()
                for time_f in vol_data:
                    if time_f > timept:
                        break
                    time_i = time_f
                # Linearly interpolate
                part_dist = self._chart_info.get_distance(time_i, timept)
                total_dist = self._chart_info.get_distance(time_i, time_f)
                position = interpolate(
                    EasingType.LINEAR, part_dist, total_dist,
                    vol_data[time_i].end, vol_data[time_f].start)
                new_ease_points[vol_name].append((timept, VolInfo(
                    position, position,
                    ease_type=easing_type,
                    filter_index=vol_data[time_i].filter_index,
                    point_type=SegmentFlag.MIDDLE,
                    wide_laser=vol_data[time_i].wide_laser)))
        # Append and sort
        for vol_name in ['vol_l', 'vol_r']:
            self._vols[vol_name] = dict(sorted(itertools.chain(
                self._vols[vol_name].items(), new_ease_points[vol_name])))

        for vol_name, vol_data in self._vols.items():
            if not vol_data:
                continue
            time_list = list(vol_data.keys())
            for time_i, time_f in itertools.pairwise(time_list):
                vol_i, vol_f = vol_data[time_i], vol_data[time_f]
                # Mark laser points as end of segment
                if vol_f.point_type == SegmentFlag.START:
                    vol_i.point_type |= SegmentFlag.END
                    continue
                # Interpolate lasers (no interpolation done if the first point is an endpoint)
                if vol_i.ease_type != EasingType.NO_EASING:
                    limit_bot, limit_top = self._ease_ranges.get(time_i, (0.0, 1.0))
                    total_span = self._chart_info.get_distance(time_i, time_f)
                    div_count = int(total_span / INTERPOLATION_DISTANCE)
                    if div_count * INTERPOLATION_DISTANCE < total_span:
                        div_count += 1
                    for i in range(1, div_count):
                        cur_span = INTERPOLATION_DISTANCE * i
                        timept = self._chart_info.add_duration(time_i, cur_span)
                        position = interpolate(
                            vol_i.ease_type, cur_span, total_span, vol_i.end, vol_f.start, limit_bot, limit_top)
                        vol_data[timept] = VolInfo(
                            position, position,
                            spin_type=SpinType.NO_SPIN,
                            spin_duration=0,
                            ease_type=vol_i.ease_type,
                            filter_index=vol_i.filter_index,
                            point_type=SegmentFlag.MIDDLE,
                            wide_laser=vol_i.wide_laser,
                            interpolated=True)
            vol_data[time_f].point_type |= SegmentFlag.END
            logger.debug(f'{vol_name} last point: {time_f}, {vol_f}')

        # Insert laser midpoints where filter type changes
        for vol_data in self._vols.values():
            new_points: dict[TimePoint, VolInfo] = {}
            for timept, filter_index in self._chart_info.active_filter.items():
                if timept not in vol_data:
                    time_i = TimePoint()
                    for time_f in vol_data:
                        if time_f > timept:
                            break
                        time_i = time_f
                    # Ignore filter changes before the start of the chart
                    if time_i == TimePoint():
                        continue
                    # Ignore filter changes after there's no more lasers
                    if time_i == time_f:
                        continue
                    # Ignore filter changes between segments
                    if SegmentFlag.END in vol_data[time_i].point_type:
                        continue
                    part_dist = self._chart_info.get_distance(time_i, timept)
                    total_dist = self._chart_info.get_distance(time_i, time_f)
                    position = interpolate(
                        EasingType.LINEAR, part_dist, total_dist,
                        vol_data[time_i].end, vol_data[time_f].start)
                    new_points[timept] = VolInfo(
                        position, position,
                        ease_type=vol_data[time_i].ease_type,
                        filter_index=filter_index,
                        point_type=SegmentFlag.MIDDLE,
                        wide_laser=vol_data[time_i].wide_laser)
                else:
                    vol_data[timept].filter_index = filter_index
                    vol_data[timept].interpolated = False
            vol_data.update(new_points)

        # Add final point for zooms
        end_point = TimePoint(self._chart_info.end_measure, 0, 1)
        zt_end = self._chart_info.spcontroller_data.zoom_top[self._final_zoom_top_timepoint].duplicate()
        zt_end.start = zt_end.end
        self._chart_info.spcontroller_data.zoom_top[end_point] = zt_end
        zb_end = self._chart_info.spcontroller_data.zoom_bottom[self._final_zoom_bottom_timepoint].duplicate()
        zb_end.start = zb_end.end
        self._chart_info.spcontroller_data.zoom_bottom[end_point] = zb_end

        # Mark first lane split point as start and add final point
        if self._first_lane_split_timepoint is not None and self._final_lane_split_timepoint is not None:
            first_timept = self._first_lane_split_timepoint
            self._chart_info.spcontroller_data.lane_split[first_timept].point_type |= SegmentFlag.START
            final_timept = self._final_lane_split_timepoint
            ls_end = self._chart_info.spcontroller_data.lane_split[final_timept].duplicate()
            ls_end.start = ls_end.end
            self._chart_info.spcontroller_data.lane_split[end_point] = ls_end

        # Mark tilt and lane split points as end of segment
        for data_dict in [self._chart_info.spcontroller_data.tilt, self._chart_info.spcontroller_data.lane_split]:
            timepts = list(data_dict.keys())
            if timepts:
                for time_i, time_f in itertools.pairwise(timepts):
                    if data_dict[time_f].point_type == SegmentFlag.START:
                        data_dict[time_i].point_type |= SegmentFlag.END
                data_dict[time_f].point_type |= SegmentFlag.END

        # Convert detected FX list into effect instances
        if len(self._fx_list) > 12:
            logger.warning(f'found more than 12 distinct effects')
            while len(self._chart_info.effect_list) < len(self._fx_list):
                index = len(self._chart_info.effect_list)
                self._chart_info.effect_list.append(effects.EffectEntry())
                self._chart_info.autotab_list.append(
                    filters.AutoTabEntry(
                        filters.AutoTabSetting(index),
                        filters.AutoTabSetting(index)))
        for i, fx_entry in enumerate(self._fx_list):
            if ';' in fx_entry:
                fx_name, *fx_params_str = fx_entry.split(';')
            else:
                fx_name, fx_params_str = fx_entry, []
            try:
                fx_params = [int(s) for s in fx_params_str]
            except ValueError:
                logger.warning(f'cannot convert effect parameters "{fx_entry}" to int')
                fx_params = []
            effect: effects.Effect
            if fx_name in KSH_EFFECT_MAP:
                effect = KSH_EFFECT_MAP[fx_name].duplicate()
            # Custom effect -- check definitions
            else:
                effect = self._chart_info._custom_effect[fx_name].duplicate()
            effect.map_params(fx_params)
            self._chart_info.effect_list[i] = effects.EffectEntry(effect)

        # Remove filters that are unused
        for filter_name in list(self._chart_info._custom_filter):
            if filter_name not in self._filter_names.values():
                del self._chart_info._custom_filter[filter_name]

        # Write custom filter as FX
        # TODO: Try matching with existing effects
        if len(self._fx_list) + len(self._chart_info._custom_filter) > 12:
            logger.warning(f'including custom filters causes more than 12 distinct effects')
            while len(self._chart_info.effect_list) < len(self._fx_list) + len(self._chart_info._custom_filter):
                index = len(self._chart_info.effect_list)
                self._chart_info.effect_list.append(effects.EffectEntry())
                self._chart_info.autotab_list.append(
                    filters.AutoTabEntry(
                        filters.AutoTabSetting(index),
                        filters.AutoTabSetting(index)))
        for i, name in enumerate(self._chart_info._custom_filter):
            filter_effect = self._chart_info._custom_filter[name]
            self._chart_info.effect_list[len(self._fx_list) + i] = effects.EffectEntry(filter_effect)
            self._filter_to_effect[name] = len(self._fx_list) + i

        # Write track auto tab info
        filter_timepts = list(self._filter_names.keys())
        for time_i, time_f in itertools.pairwise(filter_timepts):
            filter_i = self._filter_names[time_i]
            if filter_i in FILTER_TYPE_MAP:
                continue
            self._chart_info.autotab_infos[time_i] = AutoTabInfo(
                self._filter_to_effect[filter_i], self._chart_info.get_distance(time_i, time_f))

    def _parse_measure(self, measure: list[str], m_no: int, m_linecount: int) -> None:
        # Check time signatures that get pushed to the next measure
        if TimePoint(m_no, 0, 1) in self._chart_info.timesigs:
            self._cur_timesig = self._chart_info.timesigs[TimePoint(m_no, 0, 1)]

        noteline_count = 0
        for line in measure:
            subdivision = Fraction(1 * self._cur_timesig.upper, m_linecount * self._cur_timesig.lower)
            cur_subdiv  = noteline_count * subdivision
            cur_time    = TimePoint(m_no, cur_subdiv.numerator, cur_subdiv.denominator)

            # 1. Comment
            if line.startswith('//'):
                try:
                    self._handle_notechart_custom_commands(line, cur_time)
                except ValueError as e:
                    logger.warning(str(e))
            # 2. Metadata
            elif '=' in line:
                try:
                    self._handle_notechart_metadata(line, cur_time, m_no)
                except ValueError as e:
                    logger.warning(str(e))
            # 3. Notedata
            else:
                self._handle_notechart_notedata(line, cur_time, subdivision)
                noteline_count += 1

    def _parse_definitions(self) -> None:
        ln_offset: int = len(self._raw_metadata) + len(self._raw_notedata) + 1
        for line_no, line in enumerate(self._raw_definitions):
            if not line.startswith('#'):
                logger.warning(f'unrecognized line at line {ln_offset + line_no + 1}: "{line}"')
                continue
            line_type, name, definition = re.split(r'\s+', line[1:])
            params_list = [s.split('=', 1) for s in definition.split(';')]
            params_dict: dict[str, str] = {s[0]: s[1] for s in params_list}
            if 'type' not in params_dict:
                logger.warning(
                    f'ignoring definition at line {ln_offset + line_no + 1}; "type" parameter missing: "{line}"',
                    ParserWarning)
                continue
            try:
                # TODO: Better handling of custom filter and effects
                for key, val in list(params_dict.items()):
                    if '>' in val:
                        params_dict[key] = val.split('>')[1]
                    # For now I ignore figuring out which parameter changes
                    if '-' in val:
                        dash_count = val.count('-')
                        # Remove cases where range is specified
                        if dash_count > 1 or (dash_count == 1 and not val.startswith('-')):
                            del params_dict[key]
                if line_type == 'define_fx':
                    self._chart_info._custom_effect[name] = effects.from_definition(params_dict)
                elif line_type == 'define_filter':
                    self._chart_info._custom_filter[name] = effects.from_definition(params_dict)
                else:
                    logger.warning(
                        f'unrecognized definition at line {ln_offset + line_no + 1}: "{definition}"', ParserWarning)
            except ValueError as e:
                logger.warning(
                    f'ignoring definition at line {ln_offset + line_no + 1}; unable to parse definition: "{line}"',
                    ParserWarning)
                logger.warning(f'this is caused by: {e}')

    def write_xml(self, f: TextIO):
        f.write(f'  <music id="{self._song_info.id}">\n'
                 '    <info>\n'
                f'      <label>{self._song_info.id}</label>\n'
                f'      <title_name>{escape(self._song_info.title)}</title_name>\n'
                f'      <title_yomigana>{self._song_info.title_yomigana}</title_yomigana>\n'
                f'      <artist_name>{escape(self._song_info.artist)}</artist_name>\n'
                f'      <artist_yomigana>{self._song_info.artist_yomigana}</artist_yomigana>\n'
                f'      <ascii>{self._song_info.ascii_label}</ascii>\n'
                f'      <bpm_max __type="u32">{self._song_info.max_bpm * 100:.0f}</bpm_max>\n'
                f'      <bpm_min __type="u32">{self._song_info.min_bpm * 100:.0f}</bpm_min>\n'
                f'      <distribution_date __type="u32">{self._song_info.release_date}</distribution_date>\n'
                f'      <volume __type="u16">{self._song_info.music_volume}</volume>\n'
                f'      <bg_no __type="u16">{self._song_info.background.value}</bg_no>\n'
                 '      <genre __type="u8">32</genre>\n'
                 '      <is_fixed __type="u8">1</is_fixed>\n'
                 '      <version __type="u8">6</version>\n'
                 '      <demo_pri __type="s8">-2</demo_pri>\n'
                f'      <inf_ver __type="u8">{self._song_info.inf_ver.value}</inf_ver>\n'
                 '    </info>\n'
                 '    <difficulty>\n')

        for diff in DifficultySlot:
            f.write(f'      <{diff.name.lower()}>\n')
            if self._chart_info.difficulty == diff:
                f.write(f'        <difnum __type="u8">{self._chart_info.level}</difnum>\n'
                        f'        <illustrator>{escape(self._chart_info.illustrator)}</illustrator>\n'
                        f'        <effected_by>{escape(self._chart_info.effector)}</effected_by>\n'
                         '        <price __type="s32">-1</price>\n'
                         '        <limited __type="u8">3</limited>\n'
                         '        <jacket_print __type="s32">-2</jacket_print>\n'
                         '        <jacket_mask __type="s32">0</jacket_mask>\n'
                        f'        <max_exscore __type="s32">{self._chart_info.max_ex_score}</max_exscore>\n'
                         '        <radar>\n'
                        f'          <notes __type="u8">{self._chart_info.radar_notes}</notes>\n'
                        f'          <peak __type="u8">{self._chart_info.radar_peak}</peak>\n'
                        f'          <tsumami __type="u8">{self._chart_info.radar_tsumami}</tsumami>\n'
                        f'          <tricky __type="u8">{self._chart_info.radar_tricky}</tricky>\n'
                        f'          <hand-trip __type="u8">{self._chart_info.radar_handtrip}</hand-trip>\n'
                        f'          <one-hand __type="u8">{self._chart_info.radar_onehand}</one-hand>\n'
                         '        </radar>\n')
            else:
                f.write('        <difnum __type="u8">0</difnum>\n'
                        '        <illustrator>dummy</illustrator>\n'
                        '        <effected_by>dummy</effected_by>\n'
                        '        <price __type="s32">-1</price>\n'
                        '        <limited __type="u8">3</limited>\n'
                        '        <jacket_print __type="s32">-2</jacket_print>\n'
                        '        <jacket_mask __type="s32">0</jacket_mask>\n'
                        '        <max_exscore __type="s32">0</max_exscore>\n'
                        '        <radar>\n'
                        '          <notes __type="u8">0</notes>\n'
                        '          <peak __type="u8">0</peak>\n'
                        '          <tsumami __type="u8">0</tsumami>\n'
                        '          <tricky __type="u8">0</tricky>\n'
                        '          <hand-trip __type="u8">0</hand-trip>\n'
                        '          <one-hand __type="u8">0</one-hand>\n'
                        '        </radar>\n')
            f.write(f'      </{diff.name.lower()}>\n')
        f.write('    </difficulty>\n'
                '  </music>\n')

    def _write_vol(self, f: TextIO, notedata: dict[TimePoint, VolInfo], apply_ease: bool):
        for timept, vol in notedata.items():
            if not apply_ease and vol.interpolated:
                continue
            wide_indicator = 2 if vol.wide_laser else 1
            # Not slam
            if vol.start == vol.end:
                f.write('\t'.join([
                    f'{self._chart_info.timepoint_to_vox(timept)}',
                    f'{float(vol.start):.6f}',
                    f'{vol.point_type.value}',
                    f'{vol.spin_type.value}',
                    f'{vol.filter_index.value}',
                    f'{wide_indicator}',
                     '0',
                    f'{vol.ease_type.value}',
                    f'{vol.spin_duration}\n',
                ]))
            # Slam
            else:
                vol_flag_start = 1 if SegmentFlag.START in vol.point_type else 0
                vol_flag_end = 2 if SegmentFlag.END in vol.point_type else 0
                f.write('\t'.join([
                    f'{self._chart_info.timepoint_to_vox(timept)}',
                    f'{float(vol.start):.6f}',
                    f'{vol_flag_start}',
                    f'{vol.spin_type.value}',
                    f'{vol.filter_index.value}',
                    f'{wide_indicator}',
                     '0',
                    f'{vol.ease_type.value}',
                    f'{vol.spin_duration}\n',
                ]))
                f.write('\t'.join([
                    f'{self._chart_info.timepoint_to_vox(timept)}',
                    f'{float(vol.end):.6f}',
                    f'{vol_flag_end}',
                     '0',
                    f'{vol.filter_index.value}',
                    f'{wide_indicator}',
                     '0',
                    f'{vol.ease_type.value}',
                     '0\n',
                ]))

    def _write_fx(self, f: TextIO, notedata: dict[TimePoint, FXInfo]):
        for timept, fx in notedata.items():
            if fx.duration == 0:
                f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{fx.duration_as_tick()}\t{fx.special}\n')
            else:
                f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{fx.duration_as_tick()}\t{fx.special + 2}\n')

    def _write_bt(self, f: TextIO, notedata: dict[TimePoint, BTInfo]):
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
        current_bpm = self._song_info.min_bpm
        is_stop_active = False
        for timept in sorted(timepoint_set):
            if timept in self._chart_info.bpms:
                current_bpm = self._chart_info.bpms[timept]
            if timept in self._chart_info.stops:
                is_stop_active = self._chart_info.stops[timept]
            f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{current_bpm:.2f}\t4')
            if is_stop_active:
                f.write('-')
            f.write('\n')
        f.write('#END\n')
        f.write('\n')

        # Tilt modes
        f.write('#TILT MODE INFO\n')
        prev_tilt_type: TiltType | None = None
        for timept, tilt_type in self._chart_info.tilt_type.items():
            if tilt_type != prev_tilt_type:
                f.write(f'{self._chart_info.timepoint_to_vox(timept)}\t{tilt_type.value}\n')
            prev_tilt_type = tilt_type
        f.write('#END\n')
        f.write('\n')

        # Lyric info (unused)
        f.write('#LYRIC INFO\n'
                '#END\n'
                '\n')

        # End position
        f.write('#END POSITION\n'
               f'{self._chart_info.end_measure:03},01,00\n'
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

        # Tab parameters (FX on lasers parameters)
        f.write('#TAB PARAM ASSIGN INFO\n')
        for autotab in self._chart_info.autotab_list:
            f.write(autotab.to_vox_string())
        f.write('#END\n')
        f.write('\n')

        # Reverb effect param (unused)
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
        self._write_vol(f, self._chart_info.note_data.vol_l, apply_ease=True)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK2\n')
        self._write_fx(f, self._chart_info.note_data.fx_l)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK3\n')
        self._write_bt(f, self._chart_info.note_data.bt_a)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK4\n')
        self._write_bt(f, self._chart_info.note_data.bt_b)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK5\n')
        self._write_bt(f, self._chart_info.note_data.bt_c)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK6\n')
        self._write_bt(f, self._chart_info.note_data.bt_d)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK7\n')
        self._write_fx(f, self._chart_info.note_data.fx_r)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        f.write('#TRACK8\n')
        self._write_vol(f, self._chart_info.note_data.vol_r, apply_ease=True)
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        # Track auto tab (FX on lasers activation)
        f.write('#TRACK AUTO TAB\n')
        for timept, autotab_info in self._chart_info.autotab_infos.items():
            tick_amt = round(192 * autotab_info.duration)
            f.write('\t'.join([
                f'{self._chart_info.timepoint_to_vox(timept)}',
                f'{tick_amt}',
                f'{autotab_info.which + 2}\n',
            ]))
        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n'
                '\n')

        # Original TRACK1/8
        f.write('#TRACK ORIGINAL L\n')
        self._write_vol(f, self._chart_info.note_data.vol_l, apply_ease=False)
        f.write('#END\n')
        f.write('\n')

        f.write('#TRACK ORIGINAL R\n')
        self._write_vol(f, self._chart_info.note_data.vol_r, apply_ease=False)
        f.write('#END\n')
        f.write('\n')

        # == SPCONTROLER INFO == (sic)
        f.write('//====================================\n'
                '// SPCONTROLER INFO\n'
                '//====================================\n'
                '\n')

        # SPController data and default stuff I never tried to figure out
        f.write('#SPCONTROLER\n')
        f.write('001,01,00\tRealize	3\t0\t36.12\t60.12\t110.12\t0.00\n'
                '001,01,00\tRealize	4\t0\t0.62\t0.72\t1.03\t0.00\n'
                '001,01,00\tAIRL_ScaX\t1\t0\t0.00\t1.00\t0.00\t0.00\n'
                '001,01,00\tAIRR_ScaX\t1\t0\t0.00\t2.00\t0.00\t0.00\n')

        # Zoom top    -> CAM_RotX
        # Zoom bottom -> CAM_Radi
        data_dict: dict[TimePoint, SPControllerInfo]
        keyword: str
        for data_dict, keyword in [
            (self._chart_info.spcontroller_data.zoom_top, 'CAM_RotX'),
            (self._chart_info.spcontroller_data.zoom_bottom, 'CAM_Radi'),
        ]:
            keys = list(data_dict.keys())
            for timept_i, timept_f in itertools.pairwise(keys):
                z_i = data_dict[timept_i]
                z_f = data_dict[timept_f]
                if z_i.is_snap():
                    f.write('\t'.join([
                        f'{self._chart_info.timepoint_to_vox(timept_i)}',
                        keyword,
                        '2',
                        '0',
                        f'{z_i.start:.2f}',
                        f'{z_i.end:.2f}',
                        '0.00',
                        '0.00\n',
                    ]))
                tick_amt = round(192 * self._chart_info.get_distance(timept_i, timept_f))
                f.write('\t'.join([
                    f'{self._chart_info.timepoint_to_vox(timept_i)}',
                    keyword,
                    '2',
                    f'{tick_amt}',
                    f'{z_i.end:.2f}',
                    f'{z_f.start:.2f}',
                    '0.00',
                    '0.00\n',
                ]))

        # Tilt info  -> Tilt
        # Lane split -> Morphing2
        for data_dict, keyword in [
            (self._chart_info.spcontroller_data.tilt, 'Tilt'),
            (self._chart_info.spcontroller_data.lane_split, 'Morphing2'),
        ]:
            keys = list(data_dict.keys())
            for timept_i, timept_f in itertools.pairwise(keys):
                sp_i = data_dict[timept_i]
                sp_f = data_dict[timept_f]
                if sp_i.is_snap():
                    point_flag = (1 if sp_i.point_type == SegmentFlag.POINT else
                                  2 if SegmentFlag.START in sp_i.point_type else
                                  3 if SegmentFlag.END in sp_i.point_type else 0)
                    f.write('\t'.join([
                        f'{self._chart_info.timepoint_to_vox(timept_i)}',
                        keyword,
                        '2',
                        '0',
                        f'{sp_i.start:.2f}',
                        f'{sp_i.end:.2f}',
                        f'{point_flag:.2f}',
                        '0.00\n',
                    ]))
                # Don't add another entry if sp_i is the tail end of a segment
                if SegmentFlag.END in sp_i.point_type:
                    continue
                point_flag = (1 if SegmentFlag.START in sp_i.point_type and SegmentFlag.END in sp_f.point_type and not sp_f.is_snap() else
                              2 if SegmentFlag.START in sp_i.point_type and (sp_f.is_snap() or (not sp_f.is_snap() and SegmentFlag.END not in sp_f.point_type)) else
                              3 if sp_i.point_type == SegmentFlag.MIDDLE and (not sp_f.is_snap() and SegmentFlag.END in sp_f.point_type) else 0)
                tick_amt = round(192 * self._chart_info.get_distance(timept_i, timept_f))
                f.write('\t'.join([
                    f'{self._chart_info.timepoint_to_vox(timept_i)}',
                    keyword,
                    '2',
                    f'{tick_amt}',
                    f'{sp_i.end:.2f}',
                    f'{sp_f.start:.2f}',
                    f'{point_flag:.2f}',
                    '0.00\n',
                ]))

        f.write('#END\n')
        f.write('\n')

        f.write('//====================================\n')

    @property
    def ksh_path(self):
        return self._ksh_path

    @property
    def song_info(self):
        return self._song_info

    @property
    def chart_info(self):
        return self._chart_info
