from abc import abstractmethod, abstractproperty
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from warnings import warn

from .base import ParserWarning, VoxEntity
from ..utils import parse_decibel, parse_frequency, parse_length, parse_time


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

    @staticmethod
    @abstractmethod
    def from_dict(s: Mapping[str, str]):
        pass

    @abstractmethod
    def map_params(self, s: Sequence[int]) -> None:
        pass

    @abstractmethod
    def to_vox_string(self) -> str:
        pass

    def duplicate(self):
        return replace(self)


@dataclass
class NullEffect(Effect):
    @property
    def effect_index(self) -> FXType:
        return FXType.NO_EFFECT

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return NullEffect()

    def map_params(self, s: Sequence[int]) -> None:
        return

    def to_vox_string(self) -> str:
        return ',\t'.join([f'{self.effect_index.value}',
                            '0', '0', '0', '0', '0', '0'])


@dataclass
class Retrigger(Effect):
    mix: float = 95.00
    wavelength: int = 4
    update_period: float = 2.00
    feedback: float = 1.00
    amount: float = 0.85
    decay: float = 0.15

    @property
    def effect_index(self) -> FXType:
        return FXType.RETRIGGER

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Retrigger()
        if 'updatePeriod' in s:
            effect.update_period = parse_length(s['updatePeriod'])
        if 'rate' in s:
            effect.amount = parse_length(s['rate'])
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.wavelength = int(s[0] * self.update_period / 4)

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
    wavelength: int = 16
    length: float = 2.00

    @property
    def effect_index(self) -> FXType:
        return FXType.GATE

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Gate()
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.wavelength = int(s[0] * self.length / 2)

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Flanger()
        if 'period' in s:
            effect.period = parse_length(s['period']) * 4
        if 'feedback' in s:
            effect.feedback = parse_length(s['feedback'])
        if 'stereoWidth' in s:
            effect.stereo_width = int(parse_length(s['stereoWidth']) * 100)
        if 'hiCutGain' in s:
            effect.hicut_gain = parse_decibel(s['hiCutGain'])
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        pass

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Tapestop()
        if 'speed' in s:
            effect.speed = parse_length(s['speed']) * 0.1
            effect.rate = effect.rate * 0.2
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.speed = s[0] * 0.1
        self.rate = s[0] * 0.02

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Sidechain()
        if 'period' in s:
            effect.frequency = 0.25 / parse_length(s['period'])
        if 'attackTime' in s:
            effect.attack = int(parse_time(s['attackTime']))
        if 'holdTime' in s:
            effect.hold = int(parse_time(s['holdTime']))
        if 'releaseTime' in s:
            effect.release = int(parse_time(s['releaseTime']))
        # Not actually in KSM spec
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        pass

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
    frequency: float = 4.00
    bandwidth: float = 1.40

    @property
    def effect_index(self) -> FXType:
        return FXType.WOBBLE

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Wobble()
        if 'waveLength' in s:
            effect.frequency = 0.25 / parse_length(s['waveLength'])
        if 'loFreq' in s:
            effect.low_cutoff = parse_frequency(s['loFreq'])
        if 'hiFreq' in s:
            effect.hi_cutoff = parse_frequency(s['hiFreq'])
        if 'Q' in s:
            effect.bandwidth = float(s['Q'])
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.frequency = s[0] / 4

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Bitcrush()
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.amount = s[0]

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = RetriggerEx()
        effect.update_period = 4.00
        if 'rate' in s:
            effect.amount = parse_length(s['rate'])
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 or 2 parameters (got {len(s)})', ParserWarning)
            return
        if len(s) >= 2:
            self.feedback = s[1] / 100
        self.wavelength = int(s[0] * self.update_period / 4)

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = PitchShift()
        if 'pitch' in s:
            effect.amount = int(s['pitch'])
        if 'mix' in s:
            effect.mix = parse_length(s['mix']) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            warn(f'{self.__class__.__name__} requires 1 parameter (got {len(s)})', ParserWarning)
            return
        self.amount = s[0]

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return Tapescratch()

    def map_params(self, s: Sequence[int]) -> None:
        pass

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return LowpassFilter()

    def map_params(self, s: Sequence[int]) -> None:
        pass

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

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return HighpassFilter()

    def map_params(self, s: Sequence[int]) -> None:
        pass

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
        EffectEntry(Retrigger()),
        # Re16
        EffectEntry(Retrigger(wavelength=8, decay=0.1)),
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
