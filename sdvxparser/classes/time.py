"""
Classes representing time-related entities.
"""
from dataclasses import dataclass
from fractions import Fraction

from .base import Validateable

__all__ = [
    "TimeSignature",
    "TimePoint",
]


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
