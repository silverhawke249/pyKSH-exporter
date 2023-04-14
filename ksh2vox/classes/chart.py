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
    EffectEntry,
    get_default_effects,
)
from .enums import (
    DifficultySlot,
    EasingType,
    FilterIndex,
    SpinType,
    TiltType,
)
from .filters import (
    AutoTabEntry,
    Filter,
    get_default_autotab,
    get_default_filters,
)


@dataclass
class BTInfo:
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
            raise ValueError(f'duration cannot be negative (got {self.duration})')

    def duration_as_tick(self) -> int:
        return round(192 * self.duration)


@dataclass
class FXInfo:
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
            raise ValueError(f'duration cannot be negative (got {self.duration})')
        if self.special < 0:
            raise ValueError(f'special must be positive (got {self.special})')

    def duration_as_tick(self) -> int:
        return round(192 * self.duration)


@dataclass
class VolInfo:
    start: Fraction
    end: Fraction
    spin_type: SpinType = SpinType.NO_SPIN
    spin_duration: int = 0
    ease_type: EasingType = EasingType.NO_EASING
    filter_index: FilterIndex = FilterIndex.PEAK
    is_new_segment: bool = True
    last_of_segment: bool = False
    wide_laser: bool = False

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
        if self.start == self.end and self.spin_type != SpinType.NO_SPIN:
            raise ValueError(f'spin_type must be NO_SPIN when start is equal to end (got {self.spin_type.name})')
        if self.spin_duration < 0:
            raise ValueError(f'spin_duration cannot be negative (got {self.spin_duration})')
        if self.spin_type != SpinType.NO_SPIN and self.spin_duration == 0:
            raise ValueError('spin cannot have zero duration')


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
    start: Decimal
    end: Decimal
    is_new_segment: bool = True


@dataclass
class SPControllerData:
    zoom_top   : dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    zoom_bottom: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)

    tilt: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)

    lane_split: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)
    lane_toggle: dict[TimePoint, SPControllerInfo] = field(default_factory=dict)


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
    _timesig_memo: dict[int, TimeSignature] = field(default_factory=dict, init=False, repr=False)

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

    def get_timesig(self, measure: int) -> TimeSignature:
        """ Return the prevailing time signature at the given measure. """
        if measure not in self._timesig_memo:
            prev_timesig = TimeSignature()
            for timept, timesig in self.timesigs.items():
                if timept.measure > measure:
                    break
                prev_timesig = timesig

            self._timesig_memo[measure] = prev_timesig

        return self._timesig_memo[measure]

    def timepoint_to_vox(self, timepoint: TimePoint) -> str:
        """ Convert a timepoint to string in VOX format. """
        timesig = self.get_timesig(timepoint.measure)

        note_val = Fraction(1, timesig.lower)
        div = timepoint.position // note_val
        subdiv = round(192 * (timepoint.position % note_val))

        return f'{timepoint.measure:03},{div + 1:02},{subdiv:02}'

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
