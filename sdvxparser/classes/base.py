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
