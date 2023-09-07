from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from .base import VoxEntity


class FilterType(Enum):
    PEAK = 0
    LPF = 1
    HPF = 2
    BITCRUSH = 3


@dataclass
class Filter(VoxEntity, ABC):
    @property
    @abstractmethod
    def filter_index(self) -> FilterType:
        pass

    @abstractmethod
    def to_vox_string(self) -> str:
        pass


@dataclass
class LowpassFilter(Filter):
    mix: float = 90.00
    min_cutoff: float = 400.00
    max_cutoff: float = 18000.00
    bandwidth: float = 0.70

    @property
    def filter_index(self) -> FilterType:
        return FilterType.LPF

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
    mix: float = 90.00
    min_cutoff: float = 40.00
    max_cutoff: float = 5000.00
    bandwidth: float = 0.70

    @property
    def filter_index(self) -> FilterType:
        return FilterType.HPF

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
    mix: float = 100.00
    max_amount: int = 30

    @property
    def filter_index(self) -> FilterType:
        return FilterType.BITCRUSH

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.filter_index.value}", f"{self.mix:.2f}", f"{self.max_amount}"])


def get_default_filters() -> list[Filter]:
    return [
        LowpassFilter(),
        LowpassFilter(min_cutoff=600.00, max_cutoff=15000.00, bandwidth=5.00),
        HighpassFilter(),
        HighpassFilter(max_cutoff=2000.00, bandwidth=3.00),
        BitcrushFilter(),
    ]


@dataclass
class AutoTabSetting(VoxEntity):
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
    effect1: AutoTabSetting
    effect2: AutoTabSetting

    def to_vox_string(self) -> str:
        return f"{self.effect1.to_vox_string()}\n" f"{self.effect1.to_vox_string()}\n"


def get_default_autotab() -> list[AutoTabEntry]:
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
