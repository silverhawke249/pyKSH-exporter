import itertools
import logging

from dataclasses import dataclass, field, InitVar
from decimal import Decimal
from fractions import Fraction
from typing import Any

from .base import (
    AutoTabInfo,
    TimePoint,
    TimeSignature,
)
from .effects import (
    Effect,
    EffectEntry,
    get_default_effects,
)
from .enums import (
    DifficultySlot,
    EasingType,
    FilterIndex,
    SegmentFlag,
    SpinType,
    TiltType,
)
from .filters import (
    AutoTabEntry,
    Filter,
    get_default_autotab,
    get_default_filters,
)
from ..utils import clamp

MIN_RADAR_VAL = 0.0
MAX_RADAR_VAL = 200.0

logger = logging.getLogger(__name__)


@dataclass
class BTInfo:
    _duration: InitVar[Fraction | int]
    duration : Fraction = field(init=False)

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self, _duration):
        self.duration = Fraction(_duration)
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if self.duration < 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')

    def duration_as_tick(self) -> int:
        return round(192 * self.duration)


@dataclass
class FXInfo:
    _duration: InitVar[Fraction | int]
    duration : Fraction = field(init=False)
    special  : int

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self, _duration):
        self.duration = Fraction(_duration)
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if self.duration < 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')
        if self.special < 0:
            raise ValueError(f'special must be positive (got {self.special})')

    def duration_as_tick(self) -> int:
        return round(192 * self.duration)


@dataclass
class VolInfo:
    start        : Fraction
    end          : Fraction
    spin_type    : SpinType    = SpinType.NO_SPIN
    spin_duration: int         = 0
    ease_type    : EasingType  = EasingType.NO_EASING
    filter_index : FilterIndex = FilterIndex.PEAK
    point_type   : SegmentFlag = SegmentFlag.START
    wide_laser   : bool        = False
    interpolated : bool        = False

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self):
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if not 0 <= self.start <= 1:
            raise ValueError(f'start value out of range (got {self.start})')
        if not 0 <= self.end <= 1:
            raise ValueError(f'end value out of range (got {self.end})')
        if self.spin_duration < 0:
            raise ValueError(f'spin_duration cannot be negative (got {self.spin_duration})')


@dataclass
class NoteData:
    # BT
    bt_a: dict[TimePoint, BTInfo] = field(default_factory=dict)
    bt_b: dict[TimePoint, BTInfo] = field(default_factory=dict)
    bt_c: dict[TimePoint, BTInfo] = field(default_factory=dict)
    bt_d: dict[TimePoint, BTInfo] = field(default_factory=dict)

    # FX
    fx_l: dict[TimePoint, FXInfo] = field(default_factory=dict)
    fx_r: dict[TimePoint, FXInfo] = field(default_factory=dict)

    # VOL
    vol_l: dict[TimePoint, VolInfo] = field(default_factory=dict)
    vol_r: dict[TimePoint, VolInfo] = field(default_factory=dict)


@dataclass
class SPControllerInfo:
    start     : Decimal
    end       : Decimal
    point_type: SegmentFlag = SegmentFlag.START

    def is_snap(self):
        return self.start != self.end

    def duplicate(self):
        return SPControllerInfo(self.start, self.end, self.point_type)


@dataclass
class SPControllerData:
    zoom_top   : dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    zoom_bottom: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)

    tilt: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)

    lane_split: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)


@dataclass
class ChartInfo:
    # Metadata stuff
    level      : int = 1
    difficulty : DifficultySlot = DifficultySlot.MAXIMUM
    effector   : str = 'dummy'
    illustrator: str = 'dummy'

    # To be used by converters
    music_path    : str = ''
    music_offset  : int = 0
    preview_start : int = 0
    jacket_path   : str = ''
    total_measures: int = 0

    # Calculated data
    _chip_notecount: int = -1
    _long_notecount: int = -1
    _vol_notecount : int = -1
    _radar_notes   : int = -1
    _radar_peak    : int = -1
    _radar_tsumami : int = -1
    _radar_onehand : int = -1
    _radar_handtrip: int = -1
    _radar_tricky  : int = -1

    # Song data that may change mid-song
    bpms     : dict[TimePoint, Decimal]       = field(default_factory=dict)
    timesigs : dict[TimePoint, TimeSignature] = field(default_factory=dict)
    stops    : dict[TimePoint, bool]          = field(default_factory=dict)
    tilt_type: dict[TimePoint, TiltType]      = field(default_factory=dict)

    # Effect into
    effect_list : list[EffectEntry]  = field(default_factory=list)
    filter_list : list[Filter]       = field(default_factory=list)
    autotab_list: list[AutoTabEntry] = field(default_factory=list)

    active_filter: dict[TimePoint, FilterIndex] = field(default_factory=dict)
    autotab_infos: dict[TimePoint, AutoTabInfo] = field(default_factory=dict)

    # Actual chart data
    note_data: NoteData = field(default_factory=NoteData)

    # SPController data
    spcontroller_data: SPControllerData = field(default_factory=SPControllerData)

    # Private data
    _custom_effect: dict[str, Effect]        = field(default_factory=dict, init=False, repr=False)
    _custom_filter: dict[str, Effect]        = field(default_factory=dict, init=False, repr=False)
    _filter_param : dict[str, int]           = field(default_factory=dict, init=False, repr=False)

    # Cached values
    _timesig_cache     : dict[int, TimeSignature]  = field(default_factory=dict, init=False, repr=False)
    _bpm_cache         : dict[TimePoint, Decimal]  = field(default_factory=dict, init=False, repr=False)
    _tickrate_cache    : dict[TimePoint, Fraction] = field(default_factory=dict, init=False, repr=False)
    _time_to_frac_cache: dict[TimePoint, Fraction] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        # Default values
        self.bpms[TimePoint(1, 0, 1)]          = Decimal(120)
        self.timesigs[TimePoint(1, 0, 1)]      = TimeSignature()
        self.tilt_type[TimePoint(1, 0, 1)]     = TiltType.NORMAL
        self.active_filter[TimePoint(1, 0, 1)] = 0

        self.spcontroller_data.zoom_bottom[TimePoint(1, 0, 1)] = SPControllerInfo(Decimal(), Decimal())
        self.spcontroller_data.zoom_top[TimePoint(1, 0, 1)]    = SPControllerInfo(Decimal(), Decimal())

        # Populate filter list
        self.filter_list = get_default_filters()

        # Populate effect list
        self.effect_list = get_default_effects()

        # Populate autotab list
        self.autotab_list = get_default_autotab()

    # TODO: Look into why sometimes this predicts wrong long/tsumami counts
    def _calculate_notecounts(self) -> None:
        self._chip_notecount = 0
        self._long_notecount = 0
        self._vol_notecount = 0

        # Chip and long notes
        note_dicts: list[tuple[str, dict[TimePoint, BTInfo] | dict[TimePoint, FXInfo]]] = [
            ('BT_A', self.note_data.bt_a), ('BT_B', self.note_data.bt_b), ('BT_C', self.note_data.bt_c),
            ('BT_D', self.note_data.bt_d), ('FX_L', self.note_data.fx_l), ('FX_R', self.note_data.fx_r),
        ]
        for track_name, notes in note_dicts:
            for timept, note in notes.items():
                if note.duration == 0:
                    logger.debug(f'{track_name} chip: {self.timepoint_to_vox(timept)}')
                    self._chip_notecount += 1
                else:
                    logger.debug(f'{track_name} long: {self.timepoint_to_vox(timept)}')
                    tick_rate = self.get_tick_rate(timept)
                    tick_start = self.timepoint_to_fraction(timept)
                    hold_end = self.add_duration(timept, note.duration)
                    cur_hold_ticks = 0
                    # Round up to next tick
                    if tick_start % tick_rate != 0:
                        cur_hold_ticks += 1
                        timept = self.add_duration(timept, tick_rate - (tick_start % tick_rate))
                    # Add ticks
                    while timept < hold_end:
                        cur_hold_ticks += 1
                        tick_rate = self.get_tick_rate(timept)
                        timept = self.add_duration(timept, tick_rate)
                    # Long enough holds become lenient at the end
                    if cur_hold_ticks > 5:
                        cur_hold_ticks -= 1
                    if cur_hold_ticks > 6:
                        cur_hold_ticks -= 1
                    self._long_notecount += cur_hold_ticks

        # Lasers
        for lasers in [self.note_data.vol_l, self.note_data.vol_r]:
            laser_start, laser_end = TimePoint(1, 0, 1), TimePoint(1, 0, 1)
            slam_locations: list[TimePoint] = []
            for timept, laser in lasers.items():
                # This really should only be slams
                if laser.point_type == SegmentFlag.POINT:
                    self._vol_notecount += 1
                elif laser.point_type in [SegmentFlag.START, SegmentFlag.END]:
                    if laser.start != laser.end:
                        slam_locations.append(timept)
                    if laser.point_type == SegmentFlag.START:
                        laser_start = timept
                    elif laser.point_type == SegmentFlag.END:
                        laser_end = timept
                        logger.debug(f'laser segment: {self.timepoint_to_vox(laser_start)} => {self.timepoint_to_vox(laser_end)}')
                        # Process ticks
                        tick_rate = self.get_tick_rate(laser_start)
                        tick_start = self.timepoint_to_fraction(laser_start)
                        # Round up to next tick
                        if tick_start % tick_rate != 0:
                            laser_start = self.add_duration(laser_start, tick_rate - (tick_start % tick_rate))
                        timept = laser_start
                        # Get tick locations
                        tick_locations: dict[TimePoint, bool] = {}
                        tick_keys: list[TimePoint] = []
                        while timept < laser_end:
                            tick_locations[timept] = True
                            tick_keys.append(timept)
                            tick_rate = self.get_tick_rate(timept)
                            timept = self.add_duration(timept, tick_rate)
                        # Mark ticks as "occupied" by slams
                        tick_index = -1
                        for slam in slam_locations:
                            if not tick_keys:
                                break
                            while tick_index < len(tick_keys) - 1 and tick_keys[tick_index + 1] < slam:
                                tick_index += 1
                            if tick_index == -1:
                                tick_locations[tick_keys[0]] = False
                            elif tick_index == len(tick_keys) - 1:
                                tick_rate = self.get_tick_rate(tick_keys[tick_index])
                                next_tick_timept = self.add_duration(tick_keys[tick_index], tick_rate)
                                if slam < next_tick_timept:
                                    tick_locations[tick_keys[tick_index]] = False
                            else:
                                tick_rate = self.get_tick_rate(tick_keys[tick_index])
                                halfway_timept = self.add_duration(tick_keys[tick_index], tick_rate / 2)
                                if slam <= halfway_timept:
                                    tick_locations[tick_keys[tick_index]] = False
                                if slam >= halfway_timept:
                                    tick_locations[tick_keys[tick_index + 1]] = False
                        disabled_ticks = [k for k, v in tick_locations.items() if not v]
                        if disabled_ticks:
                            logger.debug(f'disabled tick: {[self.timepoint_to_vox(t) for t in disabled_ticks]}')
                        self._vol_notecount += len(slam_locations) + sum(tick_locations.values())
                        slam_locations = []
                else:
                    if laser.start != laser.end:
                        slam_locations.append(timept)

    # Radar calculation algorithm adapted from ZR147654's code, with some adjustments.
    # As such, it will not return the same values, but it should be close enough.
    def _calculate_radar_values(self) -> None:
        self._radar_notes = 0
        self._radar_peak = 0
        self._radar_tsumami = 0
        self._radar_onehand = 0
        self._radar_handtrip = 0
        self._radar_tricky = 0

        total_chart_time = 0.0
        endpoint = TimePoint(self.total_measures, 0, 1)
        for timept_i, timept_f in itertools.pairwise([*self.bpms.keys(), endpoint]):
            # Distance is in fractions of 4 beats -- i.e. 1 distance = 4 beats
            bpm_duration = self.get_distance(timept_i, timept_f)
            # Inverse of BPM is in minutes/beat
            # Multiply that with distance to get duration in minutes
            # So we need to multiply with 60 sec/min
            # tl;dr: 1 / bpm (min/beat) * 60 (sec/min) * distance (dist) * 4 (beats/dist)
            total_chart_time += 4 * 60 * bpm_duration.numerator / bpm_duration.denominator / float(self.bpms[timept_i])

        # Short songs = smaller radar value, vice versa
        length_coefficient = total_chart_time / 118.5

        # Notes
        # Higher average NPS = higher radar value
        notes_value = self.chip_notecount / total_chart_time / 12.521 * 200
        self._radar_notes = int(clamp(notes_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

        # Peak
        # Higher peak density (over 2 seconds) = higher radar value

        # Tsumami
        # More lasers = higher radar value

        # One-hand
        # More buttons while laser movement happens = higher radar value

        # Hand-trip
        # More opposite side buttons while one-handing = higher radar value

        # Tricky
        # BPM change, camera change, tilts, spins, jacks = higher radar value

    def get_timesig(self, measure: int) -> TimeSignature:
        """ Return the prevailing time signature at the given measure. """
        if measure not in self._timesig_cache:
            prev_timesig = TimeSignature()
            for timept, timesig in self.timesigs.items():
                if timept.measure > measure:
                    break
                prev_timesig = timesig
            self._timesig_cache[measure] = prev_timesig

        return self._timesig_cache[measure]

    def get_bpm(self, timepoint: TimePoint) -> Decimal:
        if timepoint not in self._bpm_cache:
            prev_bpm = Decimal(0)
            for timept, bpm in self.bpms.items():
                if timept > timepoint:
                    break
                prev_bpm = bpm
            self._bpm_cache[timepoint] = prev_bpm

        return self._bpm_cache[timepoint]

    def get_tick_rate(self, timepoint: TimePoint) -> Fraction:
        if timepoint not in self._tickrate_cache:
            self._tickrate_cache[timepoint] = Fraction(1, 16) if self.get_bpm(timepoint) < 256 else Fraction(1, 8)

        return self._tickrate_cache[timepoint]

    def get_distance(self, a: TimePoint, b: TimePoint) -> Fraction:
        """ Calculate the distance between two timepoints as a fraction. """
        if a == b:
            return Fraction()
        if b < a:
            a, b = b, a

        distance = Fraction()
        for m_no in range(a.measure, b.measure):
            distance += self.get_timesig(m_no).as_fraction()
        distance += b.position - a.position

        return distance

    def add_duration(self, a: TimePoint, b: Fraction) -> TimePoint:
        """ Calculate the resulting timepoint after adding an amount of time to a timepoint. """
        modified_length = a.position + b

        m_no = a.measure
        while modified_length >= (m_len := self.get_timesig(m_no).as_fraction()):
            modified_length -= m_len
            m_no += 1

        return TimePoint(m_no, modified_length.numerator, modified_length.denominator)

    def timepoint_to_vox(self, timepoint: TimePoint) -> str:
        """ Convert a timepoint to string in VOX format. """
        timesig = self.get_timesig(timepoint.measure)

        note_val = Fraction(1, timesig.lower)
        div = timepoint.position // note_val
        subdiv = round(192 * (timepoint.position % note_val))

        return f'{timepoint.measure:03},{div + 1:02},{subdiv:02}'

    def timepoint_to_fraction(self, timepoint: TimePoint) -> Fraction:
        """ Convert a timepoint to a fraction representation. """
        if timepoint not in self._time_to_frac_cache:
            if timepoint == TimePoint(1, 0, 1):
                self._time_to_frac_cache[timepoint] = Fraction(0)
            elif timepoint.position == 0:
                prev_timepoint = TimePoint(timepoint.measure - 1, 0, 1)
                prev_timesig = self.get_timesig(timepoint.measure - 1)
                self._time_to_frac_cache[timepoint] = self.timepoint_to_fraction(prev_timepoint) + prev_timesig.as_fraction()
            else:
                prev_timepoint = TimePoint(timepoint.measure, 0, 1)
                self._time_to_frac_cache[timepoint] = self.timepoint_to_fraction(prev_timepoint) + timepoint.position

        return self._time_to_frac_cache[timepoint]

    @property
    def chip_notecount(self) -> int:
        if self._chip_notecount == -1:
            self._calculate_notecounts()
        return self._chip_notecount

    @property
    def long_notecount(self) -> int:
        if self._long_notecount == -1:
            self._calculate_notecounts()
        return self._long_notecount

    @property
    def vol_notecount(self) -> int:
        if self._vol_notecount == -1:
            self._calculate_notecounts()
        return self._vol_notecount

    @property
    def max_chain(self) -> int:
        return self.chip_notecount + self.long_notecount + self.vol_notecount

    @property
    def max_ex_score(self) -> int:
        return 5 * self.chip_notecount + 2 * (self.long_notecount + self.vol_notecount)

    @property
    def radar_notes(self) -> int:
        if self._radar_notes == -1:
            self._calculate_radar_values()
        return self._radar_notes

    @property
    def radar_peak(self) -> int:
        if self._radar_peak == -1:
            self._calculate_radar_values()
        return self._radar_peak

    @property
    def radar_tsumami(self) -> int:
        if self._radar_tsumami == -1:
            self._calculate_radar_values()
        return self._radar_tsumami

    @property
    def radar_onehand(self) -> int:
        if self._radar_onehand == -1:
            self._calculate_radar_values()
        return self._radar_onehand

    @property
    def radar_handtrip(self) -> int:
        if self._radar_handtrip == -1:
            self._calculate_radar_values()
        return self._radar_handtrip

    @property
    def radar_tricky(self) -> int:
        if self._radar_tricky == -1:
            self._calculate_radar_values()
        return self._radar_tricky
