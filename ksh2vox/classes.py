import dataclasses
import enum
import fractions

@dataclasses.dataclass(frozen=True)
class TimePoint:
    beat: int
    subdivision: int
    count: int

    def _validate(self):
        if self.beat < 0:
            raise ValueError(f'beat cannot be negative (got {self.beat})')
        if self.subdivision <= 0:
            raise ValueError(f'subdivision must be positive (got {self.subdivision})')
        if not 0 <= self.count < self.subdivision:
            raise ValueError(f'count is out of range (got {self.count})')

    def __post_init__(self):
        self._validate()


class FilterType(enum.Enum):
    PEAK = 0
    LPF = 2
    HPF = 4
    BITCRUSH = 5


class Button(enum.Enum):
    A = 0x1
    B = 0x2
    C = 0x4
    D = 0x8


class FX(enum.Enum):
    L = 0x1
    R = 0x2


class Volume(enum.Enum):
    L = 0
    R = 1


@dataclasses.dataclass
class BTInfo:
    which: int
    duration: int

    def _validate(self):
        if not 0 <= self.which < 16:
            raise ValueError(f'value out of range (got {self.which})')
        if self.duration <= 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')

    def __post_init__(self):
        self._validate()


@dataclasses.dataclass
class FXInfo:
    which: int
    duration: int
    special: int

    def _validate(self):
        if not 0 <= self.which < 4:
            raise ValueError(f'value out of range (got {self.which})')
        if self.duration <= 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')
        if self.special < 0:
            raise ValueError(f'special must be positive (got {self.special})')

    def __post_init__(self):
        self._validate()


@dataclasses.dataclass
class VolInfo:
    which: Volume
    position: int
    special: int

    def _validate(self):
        if not 0 <= self.which < 4:
            raise ValueError(f'value out of range (got {self.which})')
        if self.duration <= 0:
            raise ValueError(f'duration cannot be negative (got {self.duration})')
        if self.special < 0:
            raise ValueError(f'special must be positive (got {self.special})')

    def __post_init__(self):
        self._validate()


@dataclasses.dataclass()
class ChartInfo:
    bpms: dict[TimePoint, float]
    time_sigs: dict[TimePoint, fractions.Fraction]
    filter_type: dict[TimePoint, FilterType]
    bt: dict[TimePoint, BTInfo]
    fx: dict[TimePoint, FXInfo]
    vol: dict[TimePoint, VolInfo]
