from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass, field
from enum import Enum

from .base import VoxEntity


class FXType(Enum):
    NO_EFFECT    = 0
    RETRIGGER    = 1
    GATE         = 2
    FLANGER      = 3
    TAPESTOP     = 4
    SIDECHAIN    = 5
    WOBBLE       = 6
    BITCRUSH     = 7
    RETRIGGER_EX = 8
    PITCH_SHIFT  = 9
    TAPESCRATCH  = 10
    LPF          = 11
    HPF          = 12


class PassFilterType(Enum):
    LPF = 0
    HPF = 1
    BANDPASS = 2


class WaveShape(Enum):
    SAW = 0
    SQUARE = 1
    LINEAR = 2
    SINE = 3


@dataclass
class Effect(VoxEntity):
    @abstractproperty
    def effect_index(self) -> FXType:
        pass

    @abstractmethod
    def to_vox_string(self) -> str:
        pass


@dataclass
class NullEffect(Effect):
    @property
    def effect_index(self) -> FXType:
        return FXType.NO_EFFECT

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                            '0', '0', '0', '0', '0', '0'])


@dataclass
class Retrigger(Effect):
    mix: float = 95.00
    wavelength: int = 8
    update_period: float = 2.00
    feedback: float = 1.00
    amount: float = 0.85
    decay: float = 0.15

    @property
    def effect_index(self) -> FXType:
        return FXType.RETRIGGER

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.wavelength}',
                           f'{self.mix:.2f}',
                           f'{self.update_period:.2f}',
                           f'{self.feedback:.2f}',
                           f'{self.amount:.2f}',
                           f'{self.decay}'])


@dataclass
class Gate(Effect):
    mix: float = 98.00
    wavelength: int = 8
    length: float = 1.00

    @property
    def effect_index(self) -> FXType:
        return FXType.GATE

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.wavelength}',
                           f'{self.length}'])


@dataclass
class Flanger(Effect):
    # Parameter names yoinked off VoxCharger lol
    mix: float = 75.00
    period: float = 2.00
    feedback: float = 0.50
    stereo_width: int = 90
    hicut_gain: float = 1.00

    @property
    def effect_index(self) -> FXType:
        return FXType.FLANGER

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.period:.2f}',
                           f'{self.feedback:.2f}',
                           f'{self.stereo_width}',
                           f'{self.hicut_gain:.2f}'])


@dataclass
class Tapestop(Effect):
    mix: float = 100.00
    speed: float = 8.00
    rate: float = 0.40

    @property
    def effect_index(self) -> FXType:
        return FXType.TAPESTOP

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.speed:.2f}',
                           f'{self.rate:.2f}'])


@dataclass
class Sidechain(Effect):
    mix: float = 90.00
    frequency: float = 1.00
    attack: int = 45
    hold: int = 50
    release: int = 60

    @property
    def effect_index(self) -> FXType:
        return FXType.SIDECHAIN

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.frequency:.2f}',
                           f'{self.attack}',
                           f'{self.hold}',
                           f'{self.release}'])


@dataclass
class Wobble(Effect):
    mix: float = 80.00
    filter_type: PassFilterType = PassFilterType.LPF
    wave_shape: WaveShape = WaveShape.SINE
    low_cutoff: float = 500.00
    hi_cutoff: float = 18000.00
    frequency: float = 3.00
    bandwidth: float = 1.40

    @property
    def effect_index(self) -> FXType:
        return FXType.WOBBLE

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.filter_type.value}',
                           f'{self.wave_shape.value}',
                           f'{self.mix:.2f}',
                           f'{self.low_cutoff:.2f}',
                           f'{self.hi_cutoff:.2f}',
                           f'{self.frequency:.2f}',
                           f'{self.bandwidth:.2f}'])


@dataclass
class Bitcrush(Effect):
    mix: float = 100.00
    amount: int = 12

    @property
    def effect_index(self) -> FXType:
        return FXType.BITCRUSH

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.amount}'])


@dataclass
class RetriggerEx(Effect):
    # Same as Retrigger, except it samples from start of effect, instead of at beginning of update period.
    mix: float = 95.00
    wavelength: int = 8
    update_period: float = 2.00
    feedback: float = 1.00
    amount: float = 0.85
    decay: float = 0.15

    @property
    def effect_index(self) -> FXType:
        return FXType.RETRIGGER_EX

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.wavelength}',
                           f'{self.mix:.2f}',
                           f'{self.update_period:.2f}',
                           f'{self.feedback:.2f}',
                           f'{self.amount:.2f}',
                           f'{self.decay}'])


@dataclass
class PitchShift(Effect):
    mix: float = 100.00
    amount: int = 12

    @property
    def effect_index(self) -> FXType:
        return FXType.PITCH_SHIFT

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.amount}'])


@dataclass
class Tapescratch(Effect):
    mix: float = 100.00
    curve_slope: float = 5.00
    attack: float = 1.00
    hold: float = 0.10
    release: float = 1.00

    @property
    def effect_index(self) -> FXType:
        return FXType.TAPESCRATCH

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.curve_slope:.2f}',
                           f'{self.attack:.2f}',
                           f'{self.hold:.2f}',
                           f'{self.release:.2f}'])


@dataclass
class LowpassFilter(Effect):
    mix: float = 75.00
    low_cutoff: float = 400.00
    hi_cutoff: float = 900.00
    bandwidth: float = 2.00  # Haven't quite figured this one out, actually

    @property
    def effect_index(self) -> FXType:
        return FXType.LPF

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.low_cutoff:.2f}',
                           f'{self.hi_cutoff:.2f}',
                           f'{self.bandwidth:.2f}'])


@dataclass
class HighpassFilter(Effect):
    mix: float = 100.00
    cutoff: float = 2000.00
    curve_slope: float = 5.00
    bandwidth: float = 1.40

    @property
    def effect_index(self) -> FXType:
        return FXType.HPF

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                           f'{self.mix:.2f}',
                           f'{self.cutoff:.2f}',
                           f'{self.curve_slope:.2f}',
                           f'{self.bandwidth:.2f}'])


@dataclass
class EffectEntry(VoxEntity):
    effect1: Effect = field(default_factory=NullEffect)
    effect2: Effect = field(default_factory=NullEffect)

    def to_vox_string(self) -> str:
        return (f'{self.effect1.to_vox_string()}\n'
                f'{self.effect2.to_vox_string()}\n')


def get_default_effects() -> list[EffectEntry]:
    return [
        # Re8
        EffectEntry(Retrigger(wavelength=4)),
        # Re16
        EffectEntry(Retrigger(decay=0.1)),
        # Ga16
        EffectEntry(Gate()),
        # Flanger
        EffectEntry(Flanger()),
        # Re32
        EffectEntry(Retrigger(wavelength=16, amount=0.87, decay=0.13)),
        # Ga8
        EffectEntry(Gate(wavelength=4)),
        # Echo4
        EffectEntry(RetriggerEx(mix=100, wavelength=4, update_period=4, feedback=0.6, amount=1, decay=0.8)),
        # Tapestop
        EffectEntry(Tapestop()),
        # Sidechain
        EffectEntry(Sidechain()),
        # Wo12
        EffectEntry(Wobble()),
        # Re12
        EffectEntry(Retrigger(wavelength=6)),
        # Bitcrush
        EffectEntry(Bitcrush()),
    ]
