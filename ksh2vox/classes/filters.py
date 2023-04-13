from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass
from enum import Enum

from .base import VoxEntity

class FilterType(Enum):
    PEAK      = 0
    LPF       = 1
    HPF       = 2
    BITCRUSH  = 3

@dataclass
class Filter(VoxEntity):
    @abstractproperty
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
        return ',\t'.join([f'{self.filter_index.value}',
                           f'{self.mix:.2}',
                           f'{self.min_cutoff:.2}',
                           f'{self.max_cutoff:.2}',
                           f'{self.bandwidth:.2}'])

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
        return ',\t'.join([f'{self.filter_index.value}',
                           f'{self.mix:.2}',
                           f'{self.min_cutoff:.2}',
                           f'{self.max_cutoff:.2}',
                           f'{self.bandwidth:.2}'])

@dataclass
class BitcrushFilter(Filter):
    mix: float = 100.00
    max_amount: int = 30

    @property
    def filter_index(self) -> FilterType:
        return FilterType.BITCRUSH

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.filter_index.value}',
                           f'{self.mix:.2}',
                           f'{self.max_amount}'])

@dataclass
class AutoTabSetting(VoxEntity):
    effect_index: int
    param_index: int = 0
    min_value: float = 0.00
    max_value: float = 0.00

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index}',
                           f'{self.param_index}',
                           f'{self.min_value:.2f}',
                           f'{self.max_value:.2f}'])

@dataclass
class AutoTabEntry(VoxEntity):
    effect1: AutoTabSetting
    effect2: AutoTabSetting

    def to_vox_string(self) -> str:
        return (f'{self.effect1.to_vox_string()}\n'
                f'{self.effect1.to_vox_string()}\n')
