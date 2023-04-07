import dataclasses

from decimal import Decimal
from enum import Enum
from fractions import Fraction
from typing import Any


class ParserWarning(UserWarning):
    pass


# TODO: Figure this out later lol
class GameBackground(Enum):
    WHAT = 0


class InfVer(Enum):
    INFINITE = 2
    GRAVITY  = 3
    HEAVENLY = 4
    VIVID    = 5
    EXCEED   = 6


@dataclasses.dataclass()
class SongInfo:
    title: str = ''
    title_yomigana: str = ''
    artist: str = ''
    artist_yomigana: str = ''
    ascii_label: str = ''
    max_bpm: Decimal = Decimal(0)
    min_bpm: Decimal = Decimal(0)
    release_date: str = ''
    music_volume: int = 100
    background: GameBackground = GameBackground.WHAT
    inf_ver: InfVer = InfVer.INFINITE


class DifficultySlot(Enum):
    NOVICE   = 1
    ADVANCED = 2
    EXHAUST  = 3
    INFINITE = 4
    MAXIMUM  = 5


@dataclasses.dataclass(frozen=True, order=True)
class TimePoint:
    measure: int
    _count: dataclasses.InitVar[int]
    _subdivision: dataclasses.InitVar[int]
    position: Fraction = dataclasses.field(init=False)

    def __post_init__(self, _count, _subdivision):
        self.validate(_count, _subdivision)
        object.__setattr__(self, 'position', Fraction(_count, _subdivision))

    def validate(self, _count, _subdivision):
        if self.measure < 0:
            raise ValueError(f'measure cannot be negative (got {self.measure})')
        if _subdivision <= 0:
            raise ValueError(f'subdivision must be positive (got {_subdivision})')
        if _count < 0:
            raise ValueError(f'count cannot be negative (got {_count})')


@dataclasses.dataclass
class BTInfo:
    _duration: dataclasses.InitVar[Fraction | int]
    duration: Fraction = dataclasses.field(init=False)

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


@dataclasses.dataclass
class FXInfo:
    _duration: dataclasses.InitVar[Fraction | int]
    duration: Fraction = dataclasses.field(init=False)
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


# TODO: redo this with the proper index (1 = lpf, 2 = hpf, 3 = bitcrush)
class FilterType(Enum):
    PEAK = 0
    LPF = 2
    HPF = 4
    BITCRUSH = 5


class SpinType(Enum):
    NO_SPIN = 0
    SINGLE_SPIN = 1
    TRIPLE_SPIN = 4
    HALF_SPIN = 5


class EasingType(Enum):
    NO_EASING = 0
    LINEAR = 2
    EASE_IN_SINE = 4
    EASE_OUT_SINE = 5


@dataclasses.dataclass
class VolInfo:
    start: Fraction
    end: Fraction
    spin_type: SpinType = SpinType.NO_SPIN
    spin_duration: int = 0
    ease_type: EasingType = EasingType.NO_EASING
    is_new_segment: bool = True
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


@dataclasses.dataclass
class NoteData:
    # BT
    bt_a: dict[TimePoint, BTInfo] = dataclasses.field(default_factory=dict)
    bt_b: dict[TimePoint, BTInfo] = dataclasses.field(default_factory=dict)
    bt_c: dict[TimePoint, BTInfo] = dataclasses.field(default_factory=dict)
    bt_d: dict[TimePoint, BTInfo] = dataclasses.field(default_factory=dict)

    # FX
    fx_l: dict[TimePoint, FXInfo] = dataclasses.field(default_factory=dict)
    fx_r: dict[TimePoint, FXInfo] = dataclasses.field(default_factory=dict)

    # VOL
    vol_l: dict[TimePoint, VolInfo] = dataclasses.field(default_factory=dict)
    vol_r: dict[TimePoint, VolInfo] = dataclasses.field(default_factory=dict)


class FXType(Enum):
    NO_EFFECT   = 0
    RETRIGGER_1 = 1
    GATE        = 2
    FLANGER     = 3
    TAPESTOP    = 4
    SIDECHAIN   = 5
    WOBBLE      = 6
    BITCRUSHER  = 7
    RETRIGGER_2 = 8
    PITCH_SHIFT = 9
    TAPESCRATCH = 10
    LPF         = 11 # fuck around with this later (it's like 11, 75.00, 400.00, 900.00, 2.00)
    HPF         = 12


@dataclasses.dataclass
class FXParameters:
    pass


@dataclasses.dataclass
class FilterFXInfo:
    which: int
    duration: Fraction


@dataclasses.dataclass
class SPControllerInfo:
    value: Decimal
    is_new_segment: bool = True


@dataclasses.dataclass
class SPControllerData:
    zoom_top   : dict[TimePoint, SPControllerInfo] = dataclasses.field(default_factory=dict)
    zoom_bottom: dict[TimePoint, SPControllerInfo] = dataclasses.field(default_factory=dict)

    tilt: dict[TimePoint, SPControllerInfo] = dataclasses.field(default_factory=dict)

    lane_split: dict[TimePoint, SPControllerInfo] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class TimeSignature:
    upper: int = 4
    lower: int = 4

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.upper <= 0:
            raise ValueError(f'upper number must be positive (got {self.upper})')
        if self.lower <= 0:
            raise ValueError(f'lower number must be positive (got {self.lower})')


@dataclasses.dataclass()
class ChartInfo:
    # Metadata stuff
    level      : int = 1
    difficulty : DifficultySlot = DifficultySlot.MAXIMUM
    effector   : str = 'dummy'
    illustrator: str = 'dummy'

    # To be used by converters
    music_path   : str = ''
    music_offset : int = 0
    preview_start: int = 0
    jacket_path  : str = ''

    # Song data that may change mid-song
    bpms     : dict[TimePoint, Decimal] = dataclasses.field(default_factory=dict)
    time_sigs: dict[TimePoint, TimeSignature] = dataclasses.field(default_factory=dict)

    # Effect into
    fx_list     : list[FXParameters]            = dataclasses.field(default_factory=list)
    filter_types: dict[TimePoint, FilterType]   = dataclasses.field(default_factory=dict)
    filter_fx   : dict[TimePoint, FilterFXInfo] = dataclasses.field(default_factory=dict)

    # Actual chart data
    note_data: NoteData = dataclasses.field(default_factory=NoteData)

    # SPController data
    spcontroller_data: SPControllerData = dataclasses.field(default_factory=SPControllerData)

    def __post_init__(self):
        # Default values
        self.bpms[TimePoint(1, 0, 1)]         = Decimal(120)
        self.time_sigs[TimePoint(1, 0, 1)]    = TimeSignature()
        self.filter_types[TimePoint(1, 0, 1)] = FilterType.PEAK
