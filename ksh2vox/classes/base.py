from abc import ABC, abstractmethod
from dataclasses import dataclass, field, InitVar
from fractions import Fraction


class VoxEntity(ABC):
    @abstractmethod
    def to_vox_string(self) -> str:
        pass


class ParserWarning(Warning):
    pass


@dataclass(frozen=True)
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

    def as_fraction(self) -> Fraction:
        return Fraction(self.upper, self.lower)


@dataclass(frozen=True, order=True)
class TimePoint:
    measure: int
    _count: InitVar[int]
    _subdivision: InitVar[int]
    position: Fraction = field(init=False)

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


@dataclass
class AutoTabInfo:
    which: int
    duration: Fraction
