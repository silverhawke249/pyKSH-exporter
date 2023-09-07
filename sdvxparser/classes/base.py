from abc import ABC, abstractmethod
from dataclasses import dataclass
from fractions import Fraction


@dataclass
class AbstractDataclass(ABC):
    def __new__(cls, *args, **kwargs):
        if cls == AbstractDataclass or cls.__bases__[0] == AbstractDataclass:
            raise TypeError("Cannot instantiate abstract class.")
        return super().__new__(cls)


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
            raise ValueError(f"upper number must be positive (got {self.upper})")
        if self.lower <= 0:
            raise ValueError(f"lower number must be positive (got {self.lower})")

    def as_fraction(self) -> Fraction:
        return Fraction(self.upper, self.lower)


@dataclass(frozen=True, order=True)
class TimePoint:
    measure: int
    position: Fraction

    def __init__(self, measure: int | None = None, count: int | None = None, subdivision: int | None = None, /):
        if measure is None:
            measure = 1
        if count is None and subdivision is None:
            count = 0
            subdivision = 1
        elif count is not None and subdivision is not None:
            pass
        else:
            raise ValueError(f"count and division must be both given or not given")
        self.validate(measure, count, subdivision)
        object.__setattr__(self, "measure", measure)
        object.__setattr__(self, "position", Fraction(count, subdivision))

    def validate(self, measure: int, count: int, subdivision: int):
        if measure < 0:
            raise ValueError(f"measure cannot be negative (got {measure})")
        if subdivision <= 0:
            raise ValueError(f"subdivision must be positive (got {subdivision})")
        if count < 0:
            raise ValueError(f"count cannot be negative (got {count})")
