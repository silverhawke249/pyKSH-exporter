"""
Classes and functions that represent and handle audio effects.
"""
import logging

from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

from .base import VoxEntity
from ..utils import parse_decibel, parse_frequency, parse_length, parse_time

__all__ = [
    "FXType",
    "PassFilterType",
    "WaveShape",
    "Effect",
    "NoEffect",
    "Retrigger",
    "Gate",
    "Flanger",
    "Tapestop",
    "Sidechain",
    "Wobble",
    "Bitcrush",
    "RetriggerEx",
    "PitchShift",
    "Tapescratch",
    "LowpassFilter",
    "HighpassFilter",
    "EffectEntry",
    "enum_to_effect",
    "from_definition",
    "get_default_effects",
]

logger = logging.getLogger(__name__)
_enumToEffect: dict = {}


class _StringifiableEnum(Enum):
    def __str__(self) -> str:
        name_parts = [s.capitalize() for s in self.name.split("_")]
        return "".join(name_parts)


class FXType(_StringifiableEnum):
    """Enumeration for effect types."""

    NO_EFFECT = 0
    RETRIGGER = 1
    GATE = 2
    FLANGER = 3
    TAPESTOP = 4
    SIDECHAIN = 5
    WOBBLE = 6
    BITCRUSH = 7
    RETRIGGER_EX = 8
    PITCH_SHIFT = 9
    TAPESCRATCH = 10
    LOW_PASS_FILTER = 11
    HIGH_PASS_FILTER = 12


class PassFilterType(_StringifiableEnum):
    """Enumeration for pass filter type."""

    LOW_PASS = 0
    HIGH_PASS = 1
    BAND_PASS = 2


class WaveShape(_StringifiableEnum):
    """Enumeration for filter wave shape."""

    SAW = 0
    SQUARE = 1
    LINEAR = 2
    SINE = 3


@dataclass
class Effect(VoxEntity, ABC):
    """Abstract base class for effects."""

    @property
    def effect_name(self) -> str:
        """Return the effect name."""
        return str(self.effect_index)

    @property
    @abstractmethod
    def effect_index(self) -> FXType:
        """Return the enumeration value corresponding to this effect."""
        pass

    @staticmethod
    @abstractmethod
    def from_dict(s: Mapping[str, str]):
        """Create an instance of this effect from a :py:class:`dict` of parameters."""
        pass

    @abstractmethod
    def map_params(self, s: Sequence[int]) -> None:
        """
        Replace some of this instance's attributes with a sequence of parameters.

        Not all effects implement this method. If unimplemented, this method is a no-op.
        """
        pass

    @abstractmethod
    def to_vox_string(self) -> str:
        pass

    def duplicate(self):
        """Create a copy of this object."""
        return replace(self)


def _register_effect(cls):
    global _enumToEffect
    _enumToEffect[cls().effect_index] = cls

    return cls


@_register_effect
@dataclass
class NoEffect(Effect):
    """A class representing a null effect."""

    @property
    def effect_index(self) -> FXType:
        return FXType.NO_EFFECT

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return NoEffect()

    def map_params(self, s: Sequence[int]) -> None:
        return

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.effect_index.value}", "0", "0", "0", "0", "0", "0"])


@_register_effect
@dataclass
class Retrigger(Effect):
    """A class representing a retrigger effect."""

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
        if "updatePeriod" in s:
            effect.update_period = parse_length(s["updatePeriod"]) * 4
        if "waveLength" in s:
            effect.wavelength = int(effect.update_period / 4 / parse_length(s["waveLength"]))
        if "rate" in s:
            effect.amount = parse_length(s["rate"])
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.wavelength = int(s[0] * self.update_period / 4)

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.wavelength}",
                f"{self.mix:.2f}",
                f"{self.update_period:.2f}",
                f"{self.feedback:.2f}",
                f"{self.amount:.2f}",
                f"{self.decay:.2f}",
            ]
        )


@_register_effect
@dataclass
class Gate(Effect):
    """A class representing a gate effect."""

    mix: float = 98.00
    wavelength: int = 16
    length: float = 2.00

    @property
    def effect_index(self) -> FXType:
        return FXType.GATE

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Gate()
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        if "waveLength" in s:
            effect.wavelength = int(effect.length / 2 / parse_length(s["waveLength"]))
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.wavelength = int(s[0] * self.length / 2)

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.effect_index.value}", f"{self.mix:.2f}", f"{self.wavelength}", f"{self.length:.2f}"])


@_register_effect
@dataclass
class Flanger(Effect):
    """A class representing a flanger effect."""

    # Parameter names yoinked off VoxCharger lol
    mix: float = 75.00
    period: float = 2.00
    feedback: float = 0.50
    stereo_width: int = 90
    hicut_gain: float = 2.00

    @property
    def effect_index(self) -> FXType:
        return FXType.FLANGER

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Flanger()
        if "period" in s:
            effect.period = parse_length(s["period"]) * 4
        if "feedback" in s:
            effect.feedback = parse_length(s["feedback"])
        if "stereoWidth" in s:
            effect.stereo_width = int(parse_length(s["stereoWidth"]) * 100)
        if "hiCutGain" in s:
            effect.hicut_gain = parse_decibel(s["hiCutGain"])
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        pass

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.mix:.2f}",
                f"{self.period:.2f}",
                f"{self.feedback:.2f}",
                f"{self.stereo_width}",
                f"{self.hicut_gain:.2f}",
            ]
        )


@_register_effect
@dataclass
class Tapestop(Effect):
    """A class representing a tapestop effect."""

    mix: float = 100.00
    speed: float = 8.00
    rate: float = 0.40

    @property
    def effect_index(self) -> FXType:
        return FXType.TAPESTOP

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Tapestop()
        if "speed" in s:
            effect.speed = parse_length(s["speed"]) * 0.16
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.speed = s[0] * 0.16

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.effect_index.value}", f"{self.mix:.2f}", f"{self.speed:.2f}", f"{self.rate:.2f}"])


@_register_effect
@dataclass
class Sidechain(Effect):
    """A class representing a sidechain effect."""

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
        if "period" in s:
            effect.frequency = 0.25 / parse_length(s["period"])
        if "attackTime" in s:
            effect.attack = int(parse_time(s["attackTime"], s["bpm"]))
        if "holdTime" in s:
            effect.hold = int(parse_time(s["holdTime"], s["bpm"]))
        if "releaseTime" in s:
            effect.release = int(parse_time(s["releaseTime"], s["bpm"]))
        # Not actually in KSM spec
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        pass

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.mix:.2f}",
                f"{self.frequency:.2f}",
                f"{self.attack}",
                f"{self.hold}",
                f"{self.release}",
            ]
        )


@_register_effect
@dataclass
class Wobble(Effect):
    """A class representing a wobble effect."""

    mix: float = 80.00
    filter_type: PassFilterType = PassFilterType.LOW_PASS
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
        if "waveLength" in s:
            effect.frequency = 0.25 / parse_length(s["waveLength"])
        if "loFreq" in s:
            effect.low_cutoff = parse_frequency(s["loFreq"])
        if "hiFreq" in s:
            effect.hi_cutoff = parse_frequency(s["hiFreq"])
        if "Q" in s:
            effect.bandwidth = float(s["Q"])
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.frequency = s[0] / 4

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.filter_type.value}",
                f"{self.wave_shape.value}",
                f"{self.mix:.2f}",
                f"{self.low_cutoff:.2f}",
                f"{self.hi_cutoff:.2f}",
                f"{self.frequency:.2f}",
                f"{self.bandwidth:.2f}",
            ]
        )


@_register_effect
@dataclass
class Bitcrush(Effect):
    """A class representing a bitcrush effect."""

    mix: float = 100.00
    amount: int = 12

    @property
    def effect_index(self) -> FXType:
        return FXType.BITCRUSH

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = Bitcrush()
        if "reduction" in s and s["reduction"].endswith("samples"):
            effect.amount = int(s["reduction"][:-7])
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.amount = s[0]

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.effect_index.value}", f"{self.mix:.2f}", f"{self.amount}"])


@_register_effect
@dataclass
class RetriggerEx(Effect):
    """
    A class representing a retrigger effect.

    This effect samples from the start of the effect, instead of at the beginning of the update period.
    """

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
        if "waveLength" in s:
            effect.wavelength = int(1 / parse_length(s["waveLength"]))
        if "feedbackLevel" in s:
            effect.feedback = parse_length(s["feedbackLevel"])
        if "rate" in s:
            effect.amount = parse_length(s["rate"])
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 or 2 parameters (got {len(s)})")
            return
        if len(s) >= 2:
            self.feedback = s[1] / 100
        self.wavelength = int(s[0] * self.update_period / 4)

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.wavelength}",
                f"{self.mix:.2f}",
                f"{self.update_period:.2f}",
                f"{self.feedback:.2f}",
                f"{self.amount:.2f}",
                f"{self.decay:.2f}",
            ]
        )


@_register_effect
@dataclass
class PitchShift(Effect):
    """A class representing a pitch shift effect."""

    mix: float = 100.00
    amount: int = 12

    @property
    def effect_index(self) -> FXType:
        return FXType.PITCH_SHIFT

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        effect = PitchShift()
        if "pitch" in s:
            effect.amount = int(float(s["pitch"]))
        if "mix" in s:
            effect.mix = parse_length(s["mix"]) * 100
        return effect

    def map_params(self, s: Sequence[int]) -> None:
        if len(s) < 1:
            logger.warning(f"{self.__class__.__name__} requires 1 parameter (got {len(s)})")
            return
        self.amount = s[0]

    def to_vox_string(self) -> str:
        return ",\t".join([f"{self.effect_index.value}", f"{self.mix:.2f}", f"{self.amount}"])


@_register_effect
@dataclass
class Tapescratch(Effect):
    """A class representing a tapescratch effect."""

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
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.mix:.2f}",
                f"{self.curve_slope:.2f}",
                f"{self.attack:.2f}",
                f"{self.hold:.2f}",
                f"{self.release:.2f}",
            ]
        )


@_register_effect
@dataclass
class LowpassFilter(Effect):
    """A class representing a low-pass filter effect."""

    mix: float = 75.00
    low_cutoff: float = 400.00
    hi_cutoff: float = 900.00
    bandwidth: float = 2.00  # Haven't quite figured this one out, actually

    @property
    def effect_index(self) -> FXType:
        return FXType.LOW_PASS_FILTER

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return LowpassFilter()

    def map_params(self, s: Sequence[int]) -> None:
        pass

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.mix:.2f}",
                f"{self.low_cutoff:.2f}",
                f"{self.hi_cutoff:.2f}",
                f"{self.bandwidth:.2f}",
            ]
        )


@_register_effect
@dataclass
class HighpassFilter(Effect):
    """A class representing a high-pass filter effect."""

    mix: float = 100.00
    cutoff: float = 2000.00
    curve_slope: float = 5.00
    bandwidth: float = 1.40

    @property
    def effect_index(self) -> FXType:
        return FXType.HIGH_PASS_FILTER

    @staticmethod
    def from_dict(s: Mapping[str, str]):
        return HighpassFilter()

    def map_params(self, s: Sequence[int]) -> None:
        pass

    def to_vox_string(self) -> str:
        return ",\t".join(
            [
                f"{self.effect_index.value}",
                f"{self.mix:.2f}",
                f"{self.cutoff:.2f}",
                f"{self.curve_slope:.2f}",
                f"{self.bandwidth:.2f}",
            ]
        )


@dataclass
class EffectEntry(VoxEntity):
    """
    A class representing a single effect setting.

    A single effect setting consists of two effects rendered together.
    """

    effect1: Effect = field(default_factory=NoEffect)
    effect2: Effect = field(default_factory=NoEffect)

    def __str__(self) -> str:
        return f"{self.effect1.effect_name}, {self.effect2.effect_name}"

    def to_vox_string(self) -> str:
        return f"{self.effect1.to_vox_string()}\n" f"{self.effect2.to_vox_string()}\n"


def enum_to_effect(val: FXType) -> type[Effect]:
    """Return the class corresponding to an enumeration member."""
    return _enumToEffect[val]


def get_default_effects() -> list[EffectEntry]:
    """Get the default effect settings."""
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


def from_definition(definition: MutableMapping[str, str]) -> Effect:
    """Construct an effect object from a parameter-value map."""
    effect_class: type[Effect]
    if definition["type"] in ["Retrigger", "Echo"]:
        effect_class = Retrigger
        if "updatePeriod" in definition:
            value = parse_length(definition["updatePeriod"])
            if value == 0:
                effect_class = RetriggerEx
    elif definition["type"] == "Gate":
        effect_class = Gate
    elif definition["type"] == "Flanger":
        effect_class = Flanger
    elif definition["type"] == "PitchShift":
        effect_class = PitchShift
    elif definition["type"] == "BitCrusher":
        effect_class = Bitcrush
    elif definition["type"] == "Phaser":
        effect_class = Flanger
        definition["period"] = definition.get("period", "1/2")
        definition["feedback"] = definition.get("feedback", "35%")
        definition["stereo_width"] = definition.get("stereoWidth", "0%")
        definition["hicut_gain"] = definition.get("hiCutGain", "8dB")
        definition["mix"] = definition.get("mix", "50%")
    elif definition["type"] == "Wobble":
        effect_class = Wobble
    elif definition["type"] == "TapeStop":
        effect_class = Tapestop
    elif definition["type"] == "SideChain":
        effect_class = Sidechain
    else:
        logger.warning(f'custom fx not parsed: "{definition}"')
        return NoEffect()
    return effect_class.from_dict(definition)
