"""
Classes that represent chart-related entities.
"""
import itertools
import logging

from collections.abc import Iterable
from dataclasses import dataclass, field, InitVar
from decimal import Decimal
from fractions import Fraction
from typing import Any

from .base import (
    Validateable,
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
    NoteType,
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
from .time import (
    TimePoint,
    TimeSignature,
)
from ..utils import clamp

__all__ = [
    "BTInfo",
    "FXInfo",
    "VolInfo",
    "NoteData",
    "SPControllerInfo",
    "SPControllerData",
    "AutoTabInfo",
    "ChartInfo",
]

TICKS_PER_BAR = 192
"""Number of ticks in a single 4/4 bar."""

HALF_TICK_BPM_THRESHOLD = Decimal("255")
"""Threshold for the BPM at which the tick rate halves."""

MIN_RADAR_VAL = Decimal()
MAX_RADAR_VAL = Decimal("200")
NOTE_STR_FLAG_MAP = {
    NoteType.FX_L: 0o40,
    NoteType.BT_A: 0o20,
    NoteType.BT_B: 0o10,
    NoteType.BT_C: 0o04,
    NoteType.BT_D: 0o02,
    NoteType.FX_R: 0o01,
}
# fmt: off
SPIN_TYPE_MAP: dict[SpinType, tuple[Decimal, int]] = {
    SpinType.NO_SPIN      : (Decimal("0.0"),   0),
    SpinType.SINGLE_SPIN  : (Decimal("1.1"), 152),
    SpinType.SINGLE_SPIN_2: (Decimal("0.7"), 104),
    SpinType.SINGLE_SPIN_3: (Decimal("0.9"), 128),
    SpinType.TRIPLE_SPIN  : (Decimal("3.0"), 392),
    SpinType.HALF_SPIN    : (Decimal("0.5"), 128),
}
# fmt: on
ONEHAND_CHIPS_MAP = {
    0: Decimal(),
    1: Decimal("1.2132"),
    2: Decimal("1.3343"),
    3: Decimal("1.6246"),
}
ONEHAND_CHIPS_DEFAULT = Decimal("1.6365")
ONEHAND_HOLDS_MAP = {
    0: Decimal(),
    1: Decimal("0.2205"),
    2: Decimal("0.3530"),
    3: Decimal("0.5180"),
}
ONEHAND_HOLDS_DEFAULT = Decimal("0.5649")
HANDTRIP_VALUE_MAP = {
    0: Decimal(),
    1: Decimal("1.2486"),
    2: Decimal("1.4250"),
    3: Decimal("1.5113"),
}
HANDTRIP_NOTETYPES_MAP = {
    NoteType.VOL_L: {NoteType.BT_A, NoteType.BT_B, NoteType.FX_L},
    NoteType.VOL_R: {NoteType.BT_C, NoteType.BT_D, NoteType.FX_R},
}
TRICKY_CAM_FLAT_INC = Decimal("0.103")
TRICKY_JACK_DISTANCE = Decimal("15") / 130
"""Distance (in seconds) between two consecutive 1/16ths at 130bpm."""

logger = logging.getLogger(__name__)


@dataclass
class BTInfo(Validateable):
    """A class that represents a BT object."""

    _duration: InitVar[Fraction | int]
    duration: Fraction = field(init=False)

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self, _duration):
        self.duration = Fraction(_duration)
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if self.duration < 0:
            raise ValueError(f"duration cannot be negative (got {self.duration})")

    def duration_as_tick(self) -> int:
        """Convert the button duration to tick count."""
        return round(TICKS_PER_BAR * self.duration)


@dataclass
class FXInfo(Validateable):
    """A class that represents an FX object."""

    _duration: InitVar[Fraction | int]
    duration: Fraction = field(init=False)
    special: int

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self, _duration):
        self.duration = Fraction(_duration)
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if self.duration < 0:
            raise ValueError(f"duration cannot be negative (got {self.duration})")
        if self.special < 0:
            raise ValueError(f"special must be positive (got {self.special})")

    def duration_as_tick(self) -> int:
        """Convert the button duration to tick count."""
        return round(TICKS_PER_BAR * self.duration)


@dataclass
class VolInfo(Validateable):
    """A class that represents a singular point on a VOL segment."""

    start: Fraction
    end: Fraction
    spin_type: SpinType = SpinType.NO_SPIN
    spin_duration: int = 0
    ease_type: EasingType = EasingType.NO_EASING
    filter_index: FilterIndex = FilterIndex.PEAK
    point_type: SegmentFlag = SegmentFlag.START
    wide_laser: bool = False
    interpolated: bool = False

    def _setattrhook(self, __name: str, __value: Any):
        super().__setattr__(__name, __value)
        self.validate()

    def __post_init__(self):
        self.validate()
        self.__setattr__ = self._setattrhook

    def validate(self):
        if not 0 <= self.start <= 1:
            raise ValueError(f"start value out of range (got {self.start})")
        if not 0 <= self.end <= 1:
            raise ValueError(f"end value out of range (got {self.end})")
        if self.spin_duration < 0:
            raise ValueError(f"spin_duration cannot be negative (got {self.spin_duration})")


@dataclass
class NoteData:
    """A class encapsulating all the note data in a chart."""

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

    def iter_bts(self) -> Iterable[tuple[NoteType, TimePoint, BTInfo]]:
        """
        Iterate through every BT object.

        :returns: A generator that emits a 3-tuple of: note type, time point of the note object, and note object
            containing the note's data.
        """
        dicts: list[tuple[NoteType, dict]] = [
            (NoteType.BT_A, self.bt_a),
            (NoteType.BT_B, self.bt_b),
            (NoteType.BT_C, self.bt_c),
            (NoteType.BT_D, self.bt_d),
        ]
        for note_type, note_dict in dicts:
            for key, value in note_dict.items():
                yield note_type, key, value

    def iter_fxs(self) -> Iterable[tuple[NoteType, TimePoint, FXInfo]]:
        """
        Iterate through every FX object.

        :returns: A generator that emits a 3-tuple of: note type, time point of the note object, and note object
            containing the note's data.
        """
        dicts: list[tuple[NoteType, dict]] = [
            (NoteType.FX_L, self.fx_l),
            (NoteType.FX_R, self.fx_r),
        ]
        for note_type, note_dict in dicts:
            for key, value in note_dict.items():
                yield note_type, key, value

    def iter_vols(self, *, add_dummy=False) -> Iterable[tuple[NoteType, TimePoint, VolInfo]]:
        """
        Iterate through every VOL point.

        :param add_dummy: If `True`, this method will emit a dummy point at the end. This is used for pairwise
            iteration.
        :returns: A generator that emits a 3-tuple of: note type, time point of the note object, and note object
            containing the note's data.
        """
        dicts: list[tuple[NoteType, dict]] = [
            (NoteType.VOL_L, self.vol_l),
            (NoteType.VOL_R, self.vol_r),
        ]
        is_empty_loop = True
        key, value = TimePoint(), VolInfo(Fraction(), Fraction())
        for note_type, note_dict in dicts:
            for key, value in note_dict.items():
                is_empty_loop = False
                yield note_type, key, value
        if not is_empty_loop and add_dummy:
            yield NoteType.DUMMY, key, value

    def iter_buttons(self) -> Iterable[tuple[NoteType, TimePoint, BTInfo | FXInfo]]:
        """Iterate through every BT and FX object.

        :returns: A generator that emits a 3-tuple of: note type, time point of the note object, and note object
            containing the note's data."""
        dicts: list[tuple[NoteType, dict]] = [
            (NoteType.BT_A, self.bt_a),
            (NoteType.BT_B, self.bt_b),
            (NoteType.BT_C, self.bt_c),
            (NoteType.BT_D, self.bt_d),
            (NoteType.FX_L, self.fx_l),
            (NoteType.FX_R, self.fx_r),
        ]
        for note_type, note_dict in dicts:
            for key, value in note_dict.items():
                yield note_type, key, value

    def iter_notes(self) -> Iterable[tuple[NoteType, TimePoint, BTInfo | FXInfo | VolInfo]]:
        """
        Iterate through every note object and VOL point.

        :returns: A generator that emits a 3-tuple of: note type, time point of the note object, and note object
            containing the note's data.
        """
        dicts: list[tuple[NoteType, dict]] = [
            (NoteType.BT_A, self.bt_a),
            (NoteType.BT_B, self.bt_b),
            (NoteType.BT_C, self.bt_c),
            (NoteType.BT_D, self.bt_d),
            (NoteType.FX_L, self.fx_l),
            (NoteType.FX_R, self.fx_r),
            (NoteType.VOL_L, self.vol_l),
            (NoteType.VOL_R, self.vol_r),
        ]
        for note_type, note_dict in dicts:
            for key, value in note_dict.items():
                yield note_type, key, value


@dataclass
class SPControllerInfo:
    """A class that represents a value of a SPController parameter."""

    start: Decimal
    end: Decimal
    point_type: SegmentFlag = SegmentFlag.START

    def is_snap(self) -> bool:
        """Return `True` if this point has a snap/instantaneous change."""
        return self.start != self.end

    def duplicate(self) -> "SPControllerInfo":
        """Create a copy of this object."""
        return SPControllerInfo(self.start, self.end, self.point_type)


@dataclass
class SPControllerData:
    """A class that contains all configurable SPController parameters."""

    zoom_top: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    zoom_bottom: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    tilt: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    lane_split: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)

    hidden_bars: dict[TimePoint, bool] = field(default_factory=dict)
    manual_bars: list[TimePoint] = field(default_factory=list)


@dataclass
class AutoTabInfo:
    """A class for storing laser effect data."""

    which: int
    duration: Fraction


@dataclass
class ChartInfo:
    """
    A class that contains all chart data and metadata.

    Instances of this class are not intended to be modified after created by the parser classes.
    """

    # Metadata stuff
    level: int = 1
    difficulty: DifficultySlot = DifficultySlot.MAXIMUM
    effector: str = "dummy"
    illustrator: str = "dummy"

    # To be used by converters
    music_path: str = ""
    effected_path: str = ""
    music_offset: int = 0
    preview_start: int = 0
    jacket_path: str = ""
    end_measure: int = 0

    # Calculated data
    _chip_notecount: int = -1
    _long_notecount: int = -1
    _vol_notecount: int = -1
    _radar_notes: int = -1
    _radar_peak: int = -1
    _radar_tsumami: int = -1
    _radar_onehand: int = -1
    _radar_handtrip: int = -1
    _radar_tricky: int = -1

    # Song data that may change mid-song
    bpms: dict[TimePoint, Decimal] = field(default_factory=dict)
    timesigs: dict[TimePoint, TimeSignature] = field(default_factory=dict)
    stops: dict[TimePoint, bool] = field(default_factory=dict)
    tilt_type: dict[TimePoint, TiltType] = field(default_factory=dict)

    # Effect into
    effect_list: list[EffectEntry] = field(default_factory=list)
    filter_list: list[Filter] = field(default_factory=list)
    autotab_list: list[AutoTabEntry] = field(default_factory=list)

    active_filter: dict[TimePoint, FilterIndex] = field(default_factory=dict)
    autotab_infos: dict[TimePoint, AutoTabInfo] = field(default_factory=dict)

    # Actual chart data
    note_data: NoteData = field(default_factory=NoteData)

    # SPController data
    spcontroller_data: SPControllerData = field(default_factory=SPControllerData)

    # Scripting assist
    script_ids: dict[NoteType, dict[TimePoint, list[int]]] = field(default_factory=dict)

    # Private data
    # Name to effect object mapping
    _custom_effect: dict[str, Effect] = field(default_factory=dict, init=False, repr=False)
    _custom_filter: dict[str, Effect] = field(default_factory=dict, init=False, repr=False)

    # For radar calculation
    _elapsed_time: dict[TimePoint, Decimal] = field(default_factory=dict, init=False, repr=False)
    _elapsed_time_bpm: dict[TimePoint, Decimal] = field(default_factory=dict, init=False, repr=False)
    _bpm_durations: dict[Decimal, Decimal] = field(default_factory=dict, init=False, repr=False)

    # Cached values
    _timesig_cache: dict[int, TimeSignature] = field(default_factory=dict, init=False, repr=False)
    _bpm_cache: dict[TimePoint, Decimal] = field(default_factory=dict, init=False, repr=False)
    _tickrate_cache: dict[TimePoint, Fraction] = field(default_factory=dict, init=False, repr=False)
    _time_to_frac_cache: dict[TimePoint, Fraction] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        # Default values
        self.bpms[TimePoint()] = Decimal("120")
        self.timesigs[TimePoint()] = TimeSignature()
        self.tilt_type[TimePoint()] = TiltType.NORMAL
        self.active_filter[TimePoint()] = FilterIndex.PEAK

        self.spcontroller_data.zoom_bottom[TimePoint()] = SPControllerInfo(Decimal(), Decimal())
        self.spcontroller_data.zoom_top[TimePoint()] = SPControllerInfo(Decimal(), Decimal())

        # Populate filter list
        self.filter_list = get_default_filters()

        # Populate effect list
        self.effect_list = get_default_effects()

        # Populate autotab list
        self.autotab_list = get_default_autotab()

    # TODO: Look into why sometimes this predicts wrong long/tsumami counts
    def _calculate_notecounts(self) -> None:
        """
        Calculate the chart's note counts.

        This is called automatically when getting the note counts for the first time.
        """
        self._chip_notecount = 0
        self._long_notecount = 0
        self._vol_notecount = 0

        # Chip and long notes
        for note_type, timept, note in self.note_data.iter_buttons():
            if note.duration == 0:
                self._chip_notecount += 1
            else:
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
        cur_note_type: NoteType | None = None
        cur_note_type = NoteType.DUMMY
        laser_start, laser_end = TimePoint(), TimePoint()
        slam_locations: list[TimePoint] = []
        for note_type, timept, laser in self.note_data.iter_vols():
            # Reset state variables when changing tracks
            if note_type != cur_note_type:
                cur_note_type = note_type
                laser_start, laser_end = TimePoint(), TimePoint()
                slam_locations: list[TimePoint] = []
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
                    logger.debug(
                        f"laser segment: {self.timepoint_to_vox(laser_start)} => {self.timepoint_to_vox(laser_end)}"
                    )
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
                        logger.debug(f"disabled tick: {[self.timepoint_to_vox(t) for t in disabled_ticks]}")
                    self._vol_notecount += len(slam_locations) + sum(tick_locations.values())
                    slam_locations = []
            else:
                if laser.start != laser.end:
                    slam_locations.append(timept)

    # Figure out how long each particular BPM lasts
    # Helpful to figure out time elapsed for a particular note
    def _calculate_bpm_durations(self, endpoint: TimePoint) -> None:
        """
        Calculate the time elapsed between each BPM change.

        This function is a prerequisite to :meth:`~sdvxparser.classes.chart.ChartInfo._get_elapsed_time`.

        :param endpoint: The time point for the end of the chart.
        """
        running_total = Decimal()
        for timept_i, timept_f in itertools.pairwise([*self.bpms.keys(), endpoint]):
            # First BPM point should be at 001,01,00, which means elapsed time is 0 sec.
            if not self._elapsed_time_bpm:
                self._elapsed_time_bpm[timept_i] = Decimal()
            cur_bpm = self.bpms[timept_i]
            # Distance is in fractions of 4 beats -- i.e. 1 distance = 4 beats
            bpm_distance = self.get_distance(timept_i, timept_f)
            # Inverse of BPM is in minutes/beat
            # Multiply that with distance to get duration in minutes
            # So we need to multiply with 60 sec/min
            # tl;dr: 1 / bpm (min/beat) * 60 (sec/min) * distance (dist) * 4 (beats/dist)
            bpm_duration = 1 / cur_bpm * 4 * 60 * bpm_distance.numerator / bpm_distance.denominator
            if cur_bpm not in self._bpm_durations:
                self._bpm_durations[cur_bpm] = Decimal()
            self._bpm_durations[cur_bpm] += bpm_duration
            running_total += bpm_duration
            self._elapsed_time_bpm[timept_f] = running_total

        self._elapsed_time = dict(self._elapsed_time_bpm)

    def _get_elapsed_time(self, timept: TimePoint) -> Decimal:
        """Convert timepoint into seconds."""
        if timept not in self._elapsed_time:
            prev_elapsed_time = Decimal()
            prev_timept = TimePoint()
            for cur_timept, elapsed_time in self._elapsed_time.items():
                if cur_timept > timept:
                    break
                prev_elapsed_time = elapsed_time
                prev_timept = cur_timept
            # Similar calculation as in _populate_bpm_durations
            cur_bpm = self.get_bpm(prev_timept)
            note_distance_frac = self.get_distance(timept, prev_timept)
            note_distance = 1 / cur_bpm * 4 * 60 * note_distance_frac.numerator / note_distance_frac.denominator
            self._elapsed_time[timept] = prev_elapsed_time + note_distance

        return self._elapsed_time[timept]

    # Radar calculation algorithm adapted from ZR147654's code, with some adjustments.
    # As such, it will not return the same values, but it should be close enough.
    def calculate_radar_values(self) -> None:
        """
        Calculate the chart's radar values.

        This is called automatically when getting the radar values for the first time.
        """
        self._radar_notes = 0
        self._radar_peak = 0
        self._radar_tsumami = 0
        self._radar_onehand = 0
        self._radar_handtrip = 0
        self._radar_tricky = 0

        # Figure out start/endpoint
        chart_begin_timept: TimePoint | None = None
        chart_end_timept: TimePoint = TimePoint()
        for _, timept, note in self.note_data.iter_notes():
            if chart_begin_timept is None:
                chart_begin_timept = timept
            chart_begin_timept = min(timept, chart_begin_timept)
            if isinstance(note, VolInfo):
                end_timept = timept
            else:
                end_timept = self.add_duration(timept, note.duration)
            chart_end_timept = max(end_timept, chart_end_timept)
        if chart_begin_timept is None:
            chart_begin_timept = TimePoint()

        # Figure out the BPM the hi-speed setting is tuned to
        self._calculate_bpm_durations(chart_end_timept)
        standard_bpm = sorted(list(self._bpm_durations.items()), key=lambda t: (t[1], t[0]))[-1][0]
        logger.info(f"----- GENERAL INFO -----")
        logger.info(f"standard bpm: {standard_bpm:.2f}bpm")
        for bpm, duration in self._bpm_durations.items():
            logger.info(f"bpm duration: {bpm:.2f}bpm, {duration:.3f}s")

        # Calculate chart length
        chart_begin_time = self._get_elapsed_time(chart_begin_timept)
        chart_end_time = self._get_elapsed_time(chart_end_timept)
        total_chart_time = chart_end_time - chart_begin_time
        # Used to scale certain radar values inversely to song length
        time_coefficient = total_chart_time / Decimal("118.5")
        time_coefficient = clamp(time_coefficient, Decimal("1"))
        logger.info(
            f"chart span: {self.timepoint_to_vox(chart_begin_timept)} ~ {self.timepoint_to_vox(chart_end_timept)}"
        )
        logger.info(f"chart span: {chart_begin_time:.3f}s ~ {chart_end_time:.3f}s ({total_chart_time:.3f}s)")

        # Notes + Peak
        # Higher average NPS = higher "notes" value
        # Higher peak density (over 2 seconds) = higher "peak" value
        peak_flags: dict[Decimal, int] = {}
        button_count = 0
        for note_type, timept, _ in self.note_data.iter_buttons():
            button_count += 1
            # Figure out the time this particular note happens
            note_timing = self._get_elapsed_time(timept)
            if note_timing not in peak_flags:
                peak_flags[note_timing] = 0
            peak_flags[note_timing] += NOTE_STR_FLAG_MAP[note_type]

        peak_values: dict[Decimal, Decimal] = {}
        for note_timing, flags in sorted(peak_flags.items()):
            peak_value = Decimal()
            # Decrease peak value when certain chords happen
            # LAB chord
            if flags & 0o70 == 0o70:
                peak_value -= Decimal("1.5")
            # 2-button chord of L, A, B
            elif any(flags & mask == mask for mask in [0o60, 0o50, 0o30]):
                peak_value -= Decimal("0.83")
            # CDR chord
            if flags & 0o07 == 0o07:
                peak_value -= Decimal("1.5")
            # 2-button chord of C, D, R
            elif any(flags & mask == mask for mask in [0o06, 0o05, 0o03]):
                peak_value -= Decimal("0.83")
            # Only applies for exactly a BC chord
            if flags == 0o14:
                peak_value -= Decimal("0.83")
            # Increase peak value by 1 for each note
            while flags:
                peak_value += flags % 2
                flags //= 2
            peak_values[note_timing] = peak_value

        # Calculate "notes" value
        # Number of chips + number of holds (not the chain from holds)
        # All these values are gonna have some adjustment coefficient that's obtained experimentally (oof)
        logger.info("----- NOTES INFO -----")
        logger.info(f"keypress count: {button_count}")
        notes_value = button_count * 200 / Decimal("12.521") / total_chart_time
        self._radar_notes = int(clamp(notes_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

        # Calculate "peak" value
        # Sum peak values over a range of 2 seconds
        # Doing it twice -- once when note is at the start of the 2sec window, once at the end
        ranged_peak_values = [
            (tn, sum((v for tr, v in peak_values.items() if 0 <= (tr - tn) <= 2), Decimal()))
            for tn in peak_values.keys()
        ]
        ranged_peak_values += [
            (tn, sum((v for tr, v in peak_values.items() if 0 <= (tn - tr) <= 2), Decimal()))
            for tn in peak_values.keys()
        ]
        peak_value = Decimal()
        peak_time = Decimal()
        for t, v in ranged_peak_values:
            if v > peak_value:
                peak_value = v
                peak_time = t
        logger.info(f"----- PEAK INFO -----")
        logger.info(f"peak value at {peak_time:.3f}s: {peak_value:.2f}")
        peak_value /= Decimal("0.24")
        self._radar_peak = int(clamp(peak_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

        # Tsumami
        # More lasers = higher radar value
        moving_laser_time = Decimal()
        static_laser_time = Decimal()
        slam_laser_time = Decimal()
        pre_laser_ranges: list[tuple[NoteType, TimePoint, TimePoint]] = []
        for vol_tuple_i, vol_tuple_f in itertools.pairwise(self.note_data.iter_vols(add_dummy=True)):
            note_type_i, timept_i, vol_data_i = vol_tuple_i
            note_type_f, timept_f, vol_data_f = vol_tuple_f
            # Add slam first before skipping
            if vol_data_i.start != vol_data_i.end:
                slam_laser_time += Decimal("0.11")
                pre_laser_ranges.append((note_type_i, timept_i, timept_i))
            # Skip if different tracks
            if note_type_i != note_type_f:
                continue
            # Skip if these segments aren't connected
            if SegmentFlag.END in vol_data_i.point_type:
                continue
            # Figure out laser duration otherwise
            vol_duration = self._get_elapsed_time(timept_f) - self._get_elapsed_time(timept_i)
            logger.debug(f"vol duration at {timept_i}: {vol_duration:.3f}s")
            if vol_data_i.end != vol_data_f.start:
                moving_laser_time += vol_duration
                pre_laser_ranges.append((note_type_i, timept_i, timept_f))
            else:
                static_laser_time += vol_duration
        # Merge coincident endpoints
        laser_ranges: list[tuple[NoteType, TimePoint, TimePoint]] = []
        prev_info: tuple[NoteType, TimePoint, TimePoint] | None = None
        for note_type, timept_i, timept_f in pre_laser_ranges:
            if prev_info is not None:
                # If current segment is coincident, extend the previous segment
                if note_type == prev_info[0] and timept_i == prev_info[2]:
                    prev_info = prev_info[0], prev_info[1], timept_f
                    continue
                # Else, previous segment is disjoint from current one
                else:
                    laser_ranges.append(prev_info)
            prev_info = note_type, timept_i, timept_f
        if prev_info is not None:
            laser_ranges.append(prev_info)
        logger.info(f"----- TSUMAMI INFO -----")
        logger.info(f"moving laser time: {moving_laser_time:.3f}s")
        logger.info(f"static laser time: {static_laser_time:.3f}s")
        logger.info(f"slam laser time: {slam_laser_time:.3f}s")
        tsumami_value = (moving_laser_time + slam_laser_time) / total_chart_time * 191
        tsumami_value += static_laser_time / total_chart_time * 29
        tsumami_value *= Decimal("0.956")
        self._radar_tsumami = int(clamp(tsumami_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

        # One-hand + Hand-trip
        # More buttons while laser movement happens = higher "one-hand" value
        # More opposite side buttons while one-handing = higher "hand-trip" value
        onehand = {
            "chip": Decimal(),
            "long": Decimal(),
        }
        handtrip = {
            "chip": Decimal(),
            "long": Decimal(),
        }
        for laser_note_type, timept_i, timept_f in laser_ranges:
            # One-hand check
            chip_timepts: dict[TimePoint, list[NoteType]] = {}
            hold_timepts: list[tuple[NoteType, TimePoint, TimePoint]] = []
            for note_type, btn_timept_i, note_data in self.note_data.iter_buttons():
                if timept_i <= btn_timept_i <= timept_f:
                    if btn_timept_i not in chip_timepts:
                        chip_timepts[btn_timept_i] = []
                    chip_timepts[btn_timept_i].append(note_type)
                if note_data.duration != 0:
                    btn_timept_f = self.add_duration(btn_timept_i, note_data.duration)
                    # Hold happens at least partially within the laser segment
                    if btn_timept_i <= timept_f or timept_i <= btn_timept_f:
                        hold_timepts.append((note_type, btn_timept_i, btn_timept_f))
            timept_check = {t for _, t, _ in hold_timepts if timept_i <= t <= timept_f}
            timept_check.add(timept_i)
            for note_list in chip_timepts.values():
                onehand_count = len(note_list)
                handtrip_count = sum(1 for nt in note_list if nt in HANDTRIP_NOTETYPES_MAP[laser_note_type])
                onehand["chip"] += ONEHAND_CHIPS_MAP.get(onehand_count, ONEHAND_CHIPS_DEFAULT)
                handtrip["chip"] += HANDTRIP_VALUE_MAP[handtrip_count]
            for timept in timept_check:
                # Count holds that are happening
                onehand_count = sum(1 for _, ti, tf in hold_timepts if ti <= timept < tf)
                handtrip_count = sum(
                    1
                    for nt, ti, tf in hold_timepts
                    if ti <= timept < tf and nt in HANDTRIP_NOTETYPES_MAP[laser_note_type]
                )
                onehand["long"] += ONEHAND_HOLDS_MAP.get(onehand_count, ONEHAND_HOLDS_DEFAULT)
                handtrip["long"] += HANDTRIP_VALUE_MAP[handtrip_count]
        logger.info(f"----- ONE-HAND INFO -----")
        logger.info(f'button tap value: {onehand["chip"]:.3f}')
        logger.info(f'button hold value: {onehand["long"]:.3f}')
        onehand_factor = (onehand["chip"] + onehand["long"]) / button_count - Decimal("0.16")
        onehand_factor /= Decimal("0.34")
        onehand_factor = clamp(onehand_factor, Decimal(), Decimal("1")) + 2
        onehand_value = (onehand["chip"] + onehand["long"]) / Decimal("5.55") * onehand_factor / time_coefficient
        self._radar_onehand = int(clamp(onehand_value, MIN_RADAR_VAL, MAX_RADAR_VAL))
        logger.info(f"----- HAND-TRIP INFO -----")
        logger.info(f'button tap value: {handtrip["chip"]:.3f}')
        logger.info(f'button hold value: {handtrip["long"]:.3f}')
        handtrip_value = (handtrip["chip"] + handtrip["long"]) / time_coefficient
        self._radar_handtrip = int(clamp(handtrip_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

        # Tricky
        # BPM change, camera change, tilts, spins, jacks = higher radar value
        tricky = {
            "camera": Decimal("0.0"),
            "notes": Decimal("0.0"),
            "bpm_change": Decimal("0.0"),
            "bpm_dev": Decimal("0.0"),
            "jacks": Decimal("0.0"),
        }
        # Lane spins
        for note_type, spin_start_t, vol in self.note_data.iter_vols():
            # We're only taking spins (which implies slams)
            if vol.start == vol.end or vol.spin_type == SpinType.NO_SPIN:
                continue
            # This is in ticks
            tricky_increment, spin_duration = SPIN_TYPE_MAP[vol.spin_type]
            camera_value = Decimal("0.82") if vol.spin_type == SpinType.HALF_SPIN else Decimal("2.2")
            # Tricky increment from spin
            tricky["camera"] += tricky_increment
            if vol.spin_duration != 0:
                spin_duration = vol.spin_duration * 48
            spin_end_t = self.add_duration(spin_start_t, spin_duration)
            # Tricky increment from camera
            button_count = sum(
                1 for _, note_t, _ in self.note_data.iter_buttons() if spin_start_t <= note_t < spin_end_t
            )
            tricky["notes"] += button_count * camera_value
        # Camera changes
        camera_dicts = [self.spcontroller_data.zoom_bottom, self.spcontroller_data.zoom_top]
        for camera_dict in camera_dicts:
            is_empty_loop = True
            cam_data_i = SPControllerInfo(Decimal(), Decimal())
            cam_data_f = SPControllerInfo(Decimal(), Decimal())
            for timept_i, timept_f in itertools.pairwise(camera_dict):
                is_empty_loop = False
                cam_data_i = camera_dict[timept_i]
                cam_data_f = camera_dict[timept_f]
                # Add tricky value for instant changes
                if cam_data_i.is_snap():
                    tricky["camera"] += TRICKY_CAM_FLAT_INC
                # Camera changes also add tricky value
                tricky["camera"] += TRICKY_CAM_FLAT_INC
                time_i = self._get_elapsed_time(timept_i)
                time_f = self._get_elapsed_time(timept_f)
                # Every note adds tricky depending on camera value
                # TODO: Optimize this
                note_timepts = [
                    note_t for _, note_t, _ in self.note_data.iter_buttons() if timept_i <= note_t < timept_f
                ]
                for note_t in note_timepts:
                    note_s = self._get_elapsed_time(note_t)
                    cam_val = (cam_data_f.start - cam_data_i.end) * (note_s - time_i) / (time_f - time_i) + (
                        cam_data_i.end
                    )
                    tricky["notes"] += abs(cam_val * 100) ** Decimal("2.5") / 2_100_000
            if not is_empty_loop and cam_data_f.is_snap():
                tricky["camera"] += TRICKY_CAM_FLAT_INC
        # Lane tilts
        tricky["camera"] += Decimal("0.002") * len(self.spcontroller_data.tilt)
        # Jacks
        last_note_type: NoteType | None = None
        last_time: Decimal | None = None
        jacks: list[int] = []
        jack_count = 1
        for note_type, timept, _ in self.note_data.iter_buttons():
            if note_type != last_note_type:
                last_note_type = note_type
                last_time = None
                # Check when we switch tracks
                if jack_count >= 3:
                    jacks.append(jack_count)
                jack_count = 1
            cur_time = self._get_elapsed_time(timept)
            if last_time is not None:
                if cur_time - last_time <= TRICKY_JACK_DISTANCE:
                    jack_count += 1
                else:
                    if jack_count >= 3:
                        jacks.append(jack_count)
                    jack_count = 1
            last_time = cur_time
        # Check for the last track
        if jack_count >= 3:
            jacks.append(jack_count)
        tricky["jacks"] += sum((v ** Decimal("1.85")) / Decimal("2.6") for v in jacks)
        # BPM changes
        tricky["bpm_change"] += Decimal("0.8") * (len(self.bpms) - 1)
        tricky["bpm_change"] += ((len(self.bpms) - 1) ** Decimal("1.155")) / time_coefficient
        for bpm_value, bpm_duration in self._bpm_durations.items():
            bpm_ratio = standard_bpm / bpm_value
            if bpm_ratio < 1:
                bpm_ratio = 1 / bpm_ratio
            elif bpm_ratio == 1:
                continue
            tricky["bpm_dev"] += 2 * (bpm_ratio ** Decimal("1.25")) * (bpm_duration ** Decimal("0.5"))
        logger.info(f"----- TRICKY INFO -----")
        logger.info(f'bpm change tricky: {tricky["bpm_change"]:.3f}')
        logger.info(f'bpm deviation tricky: {tricky["bpm_dev"]:.3f}')
        logger.info(f'baseline camera tricky: {tricky["camera"]:.3f}')
        logger.info(f'note + lane change tricky: {tricky["notes"]:.3f}')
        logger.info(f'jacks tricky: {tricky["jacks"]:.3f}')
        tricky_value = sum(tricky.values()) / time_coefficient
        self._radar_tricky = int(clamp(tricky_value, MIN_RADAR_VAL, MAX_RADAR_VAL))

    def get_timesig(self, measure: int) -> TimeSignature:
        """
        Fetch the prevailing time signature at the given measure.

        :param measure: The measure number (measure starts from 1).
        :returns: The measure's time signature.
        """
        if measure not in self._timesig_cache:
            prev_timesig = TimeSignature()
            for timept, timesig in self.timesigs.items():
                if timept.measure > measure:
                    break
                prev_timesig = timesig
            self._timesig_cache[measure] = prev_timesig

        return self._timesig_cache[measure]

    def get_bpm(self, timepoint: TimePoint) -> Decimal:
        """
        Fetch the prevailing BPM at the given time point.

        :param timepoint: The time point to query.
        :returns: The chart's BPM at that time point.
        """
        if timepoint not in self._bpm_cache:
            prev_bpm = Decimal()
            for timept, bpm in self.bpms.items():
                if timept > timepoint:
                    break
                prev_bpm = bpm
            self._bpm_cache[timepoint] = prev_bpm

        return self._bpm_cache[timepoint]

    def get_tick_rate(self, timepoint: TimePoint) -> Fraction:
        """
        Fetch the prevailing tick rate at the given time point.

        :param measure: The point to query.
        :returns: The active tick rate at that time point. Holds and lasers tick at this rate.
        """
        if timepoint not in self._tickrate_cache:
            self._tickrate_cache[timepoint] = (
                Fraction(1, 16) if self.get_bpm(timepoint) < HALF_TICK_BPM_THRESHOLD else Fraction(1, 8)
            )

        return self._tickrate_cache[timepoint]

    def get_distance(self, a: TimePoint, b: TimePoint) -> Fraction:
        """
        Calculate the distance between two timepoints as a fraction.

        :param a: The first time point.
        :param b: The second time point.
        :returns: The distance between two timepoints. This is always non-negative.
        """
        if a == b:
            return Fraction()
        if b < a:
            a, b = b, a

        distance = Fraction()
        for m_no in range(a.measure, b.measure):
            distance += self.get_timesig(m_no).as_fraction()
        distance += b.position - a.position

        return distance

    def add_duration(self, a: TimePoint, b: Fraction | int) -> TimePoint:
        """
        Calculate the resulting timepoint after adding an amount of time to a timepoint.

        If the second argument is an integer, it is assumed to be the tick count.

        :param a: The starting time point.
        :param b: The amount to add to the time point.
        :returns: The resulting time point.
        """
        if isinstance(b, Fraction):
            modified_length = a.position + b
        else:
            modified_length = a.position + Fraction(b, TICKS_PER_BAR)

        m_no = a.measure
        while modified_length >= (m_len := self.get_timesig(m_no).as_fraction()):
            modified_length -= m_len
            m_no += 1

        return TimePoint(m_no, modified_length.numerator, modified_length.denominator)

    def timepoint_to_vox(self, timepoint: TimePoint) -> str:
        """
        Convert a timepoint to string in VOX format.

        This requires the time signature data.

        :param timepoint: The time point to convert.
        :returns: A string representing the time point in VOX format.
        """
        timesig = self.get_timesig(timepoint.measure)

        note_val = Fraction(1, timesig.lower)
        div = timepoint.position // note_val
        subdiv = round(TICKS_PER_BAR * (timepoint.position % note_val))

        return f"{timepoint.measure:03},{div + 1:02},{subdiv:02}"

    def timepoint_to_fraction(self, timepoint: TimePoint) -> Fraction:
        """
        Convert a timepoint to a fraction representation.

        This requires the time signature data.

        :param timepoint: The time point to convert.
        :returns: A fraction representing the time point.
        """
        if timepoint not in self._time_to_frac_cache:
            if timepoint == TimePoint():
                self._time_to_frac_cache[timepoint] = Fraction()
            elif timepoint.position == 0:
                prev_timepoint = TimePoint(timepoint.measure - 1, 0, 1)
                prev_timesig = self.get_timesig(timepoint.measure - 1)
                self._time_to_frac_cache[timepoint] = (
                    self.timepoint_to_fraction(prev_timepoint) + prev_timesig.as_fraction()
                )
            else:
                prev_timepoint = TimePoint(timepoint.measure, 0, 1)
                self._time_to_frac_cache[timepoint] = self.timepoint_to_fraction(prev_timepoint) + timepoint.position

        return self._time_to_frac_cache[timepoint]

    @property
    def has_effected_track(self) -> bool:
        return bool(self.effected_path)

    @property
    def chip_notecount(self) -> int:
        """The number of chip notes in the chart."""
        if self._chip_notecount == -1:
            self._calculate_notecounts()
        return self._chip_notecount

    @property
    def long_notecount(self) -> int:
        """The number of long notes in the chart."""
        if self._long_notecount == -1:
            self._calculate_notecounts()
        return self._long_notecount

    @property
    def vol_notecount(self) -> int:
        """The number of laser notes in the chart."""
        if self._vol_notecount == -1:
            self._calculate_notecounts()
        return self._vol_notecount

    @property
    def max_chain(self) -> int:
        """The total chain of the chart."""
        return self.chip_notecount + self.long_notecount + self.vol_notecount

    @property
    def max_ex_score(self) -> int:
        """The total ex score of the chart."""
        return 5 * self.chip_notecount + 2 * (self.long_notecount + self.vol_notecount)

    @property
    def radar_notes(self) -> int:
        """The value of the NOTES radar."""
        if self._radar_notes == -1:
            self.calculate_radar_values()
        return self._radar_notes

    @property
    def radar_peak(self) -> int:
        """The value of the PEAK radar."""
        if self._radar_peak == -1:
            self.calculate_radar_values()
        return self._radar_peak

    @property
    def radar_tsumami(self) -> int:
        """The value of the TSUMAMI radar."""
        if self._radar_tsumami == -1:
            self.calculate_radar_values()
        return self._radar_tsumami

    @property
    def radar_onehand(self) -> int:
        """The value of the ONE-HAND radar."""
        if self._radar_onehand == -1:
            self.calculate_radar_values()
        return self._radar_onehand

    @property
    def radar_handtrip(self) -> int:
        """The value of the HAND-TRIP radar."""
        if self._radar_handtrip == -1:
            self.calculate_radar_values()
        return self._radar_handtrip

    @property
    def radar_tricky(self) -> int:
        """The value of the TRICKY radar."""
        if self._radar_tricky == -1:
            self.calculate_radar_values()
        return self._radar_tricky
