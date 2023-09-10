"""
Base, generic classes supporting other more specialized classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fractions import Fraction

__all__ = [
    "AbstractDataclass",
    "VoxEntity",
    "ParserWarning",
    "TimeSignature",
    "TimePoint",
]


@dataclass
class AbstractDataclass(ABC):
    """An abstract base class for dataclasses."""

    def __new__(cls, *args, **kwargs):
        if cls == AbstractDataclass or cls.__bases__[0] == AbstractDataclass:
            raise TypeError("Cannot instantiate abstract class.")
        return super().__new__(cls)


class VoxEntity(ABC):
    """An abstract base class for objects that directly represent an entity in VOX file format."""

    @abstractmethod
    def to_vox_string(self) -> str:
        """Convert the object to its string representation in VOX file format."""
        pass


class Validateable(ABC):
    """An abstract base class for classes that require validation."""

    @abstractmethod
    def validate(self):
        """
        Perform validation on the object.

        :raises ValueError: if any of the input is invalid.
        """
        pass


class ParserWarning(Warning):
    """Warning class for parser-related issues."""

    pass


@dataclass(frozen=True)
class TimeSignature(Validateable):
    """An immutable class that represents a time signature."""

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
        """
        Convert the time signature to a fraction.

        :returns: A :class:`~fractions.Fraction` object.
        """
        return Fraction(self.upper, self.lower)


@dataclass(frozen=True, order=True)
class TimePoint(Validateable):
    """An immutable, ordered class that represents a point in time, subject to the prevailing time signature."""

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
