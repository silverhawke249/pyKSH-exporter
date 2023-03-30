import dataclasses
import decimal
import enum
import fractions

@dataclasses.dataclass(frozen=True)
class TimePoint:
    beat: int
    subdivision: int
    count: int

    def validate(self):
        if self.beat < 0:
            raise ValueError(f'beat cannot be negative (got {self.beat})')
        if self.subdivision <= 0:
            raise ValueError(f'subdivision must be positive (got {self.subdivision})')
        if not 0 <= self.count < self.subdivision:
            raise ValueError(f'count is out of range (got {self.count})')

    # Define add, subtract, mult (with int) and div (with int)

    def __post_init__(self):
        self.validate()


class Button:
    @property
    def A():
        return 0x1

    @property
    def B():
        return 0x2

    @property
    def C():
        return 0x4

    @property
    def D():
        return 0x8


@dataclasses.dataclass
class BTInfo:
    which: int
    duration: int

    def validate(self):
        if not 0 < self.which < 16:
            raise ValueError(f'value out of range (got {self.which})')
        if self.duration <= 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')

    def __post_init__(self):
        self.validate()


class FX:
    @property
    def L():
        return 0x1

    @property
    def R():
        return 0x2


@dataclasses.dataclass
class FXInfo:
    which: int
    duration: int
    special: int

    def validate(self):
        if not 0 < self.which < 4:
            raise ValueError(f'value out of range (got {self.which})')
        if self.duration <= 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')
        if self.special < 0:
            raise ValueError(f'special must be positive (got {self.special})')

    def __post_init__(self):
        self.validate()


class FilterType(enum.Enum):
    PEAK = 0
    LPF = 2
    HPF = 4
    BITCRUSH = 5


class SpinType(enum.Enum):
    NO_SPIN = 0
    SINGLE_SPIN = 1
    TRIPLE_SPIN = 4
    HALF_SPIN = 5


class EasingType(enum.Enum):
    NO_EASING = 0
    LINEAR = 2
    EASE_IN_SINE = 4
    EASE_OUT_SINE = 5


@dataclasses.dataclass
class VolInfo:
    start: decimal.Decimal
    end: decimal.Decimal
    spin_type: SpinType
    spin_duration: int
    filter: FilterType
    ease_type: EasingType
    is_new_segment: bool = True
    wide_laser: bool = False

    def validate(self):
        if not 0 <= self.start <= 1:
            raise ValueError(f'start value out of range (got {self.start})')
        if not 0 <= self.end <= 1:
            raise ValueError(f'end value out of range (got {self.end})')
        if self.start == self.end and self.spin_type != SpinType.NO_SPIN:
            raise ValueError(f'spin_type must be NO_SPIN when start is equal end (got {self.spin_type.name})')
        if self.spin_duration < 0:
            raise ValueError(f'spin_duration cannot be negative (got {self.spin_duration})')
        if self.spin_type != SpinType.NO_SPIN and self.spin_duration == 0:
            raise ValueError('spin cannot have zero duration')

    def __post_init__(self):
        self.validate()


class FXType(enum.Enum):
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
    # UNKNOWN     = 11 (we'll figure this out some day)
    HPF         = 12


@dataclasses.dataclass
class FXParameters:
    pass


@dataclasses.dataclass
class FilterFXInfo:
    which: int
    duration: TimePoint


@dataclasses.dataclass
class SPControllerInfo:
    value: decimal.Decimal
    is_new_segment: bool = True


@dataclasses.dataclass()
class ChartInfo:
    bpms: dict[TimePoint, decimal.Decimal] = {}
    time_sigs: dict[TimePoint, fractions.Fraction] = {}

    # Effect into
    fx_list: list[FXParameters] = []
    filter_types: dict[TimePoint, FilterType] = {}
    filter_fx: dict[TimePoint] = {}

    # Actual chart data
    bt: dict[TimePoint, BTInfo] = {}
    fx: dict[TimePoint, FXInfo] = {}
    vol_l: dict[TimePoint, VolInfo] = {}
    vol_r: dict[TimePoint, VolInfo] = {}

    # SPController data
    zoom_bottom: dict[TimePoint, SPControllerInfo] = {}
    zoom_top: dict[TimePoint, SPControllerInfo] = {}
    tilt: dict[TimePoint, SPControllerInfo] = {}
    lane_split: dict[TimePoint, SPControllerInfo] = {}
