"""
Classes and functions that represent and handle filters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from .base import VoxEntity

__all__ = [
    "KSHFilterType",
    "Filter",
    "LowpassFilter",
    "HighpassFilter",
    "BitcrushFilter",
    "AutoTabSetting",
    "AutoTabEntry",
    "get_default_filters",
    "get_default_autotab",
]


class KSHFilterType(Enum):
    """Enumeration for KSH filter types."""

    PEAK = 0
    LPF = 1
    HPF = 2
    BITCRUSH = 3


@dataclass
class Filter(VoxEntity, ABC):
    """Abstract base class for laser filters."""

    @property
    @abstractmethod
    def filter_index(self) -> KSHFilterType:
        """Return the enumeration value corresponding to this filter."""
        pass

    @abstractmethod
    def to_vox_string(self) -> str:
        pass


@dataclass
class LowpassFilter(Filter):
    """A class representing a low-pass filter on lasers."""

    mix: float = 90.00
    min_cutoff: float = 400.00
    max_cutoff: float = 18000.00
    bandwidth: float = 0.70

    @property
    def filter_index(self) -> KSHFilterType:
        return KSHFilterType.LPF

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.filter_index.value}",
                f"{self.mix:.2f}",
                f"{self.min_cutoff:.2f}",
                f"{self.max_cutoff:.2f}",
                f"{self.bandwidth:.2f}",
            ]
        )


@dataclass
class HighpassFilter(Filter):
    """A class representing a high-pass filter on lasers."""

    mix: float = 90.00
    min_cutoff: float = 40.00
    max_cutoff: float = 5000.00
    bandwidth: float = 0.70

    @property
    def filter_index(self) -> KSHFilterType:
        return KSHFilterType.HPF

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.filter_index.value}",
                f"{self.mix:.2f}",
                f"{self.min_cutoff:.2f}",
                f"{self.max_cutoff:.2f}",
                f"{self.bandwidth:.2f}",
            ]
        )


@dataclass
class BitcrushFilter(Filter):
    """A class representing a bitcrush filter on lasers."""

    mix: float = 100.00
    max_amount: int = 30

    @property
    def filter_index(self) -> KSHFilterType:
        return KSHFilterType.BITCRUSH

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.filter_index.value}", f"{self.mix:.2f}", f"{self.max_amount}"])


def get_default_filters() -> list[Filter]:
    """Get the default filter settings."""
    return [
        LowpassFilter(),
        LowpassFilter(min_cutoff=600.00, max_cutoff=15000.00, bandwidth=5.00),
        HighpassFilter(),
        HighpassFilter(max_cutoff=2000.00, bandwidth=3.00),
        BitcrushFilter(),
    ]


@dataclass
class AutoTabSetting(VoxEntity):
    """
    A class that represents a single auto-tab setting.

    Auto-tab refers to applying instances of :class:`~sdvxparser.classes.effects.Effect` to laser segments.
    """

    effect_index: int  # This actually doesn't do anything, to my knowledge
    param_index: int = 0
    min_value: float = 0.00
    max_value: float = 0.00

    def to_vox_string(self) -> str:
        return ",\t".join(
            [f"{self.effect_index}", f"{self.param_index}", f"{self.min_value:.2f}", f"{self.max_value:.2f}"]
        )


@dataclass
class AutoTabEntry(VoxEntity):
    """
    A class that represents a single auto-tab entry.

    A single auto-tab entry consists of two auto-tab settings.
    """

    effect1: AutoTabSetting
    effect2: AutoTabSetting

    def to_vox_string(self) -> str:
        return f"{self.effect1.to_vox_string()}\n" f"{self.effect1.to_vox_string()}\n"


def get_default_autotab() -> list[AutoTabEntry]:
    """Get the default auto-tab settings."""
    return [
        AutoTabEntry(AutoTabSetting(0), AutoTabSetting(0)),
        AutoTabEntry(AutoTabSetting(1), AutoTabSetting(1)),
        AutoTabEntry(AutoTabSetting(2), AutoTabSetting(2)),
        AutoTabEntry(AutoTabSetting(3), AutoTabSetting(3)),
        AutoTabEntry(AutoTabSetting(4), AutoTabSetting(4)),
        AutoTabEntry(AutoTabSetting(5), AutoTabSetting(5)),
        AutoTabEntry(AutoTabSetting(6), AutoTabSetting(6)),
        AutoTabEntry(AutoTabSetting(7), AutoTabSetting(7)),
        AutoTabEntry(AutoTabSetting(8), AutoTabSetting(8)),
        AutoTabEntry(AutoTabSetting(9), AutoTabSetting(9)),
        AutoTabEntry(AutoTabSetting(10), AutoTabSetting(10)),
        AutoTabEntry(AutoTabSetting(11), AutoTabSetting(11)),
    ]
