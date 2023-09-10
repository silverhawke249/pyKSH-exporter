"""
Classes and functions that provide general utility.
"""
from abc import ABC
from decimal import Decimal
from fractions import Fraction
from math import pi, sin
from numbers import Real
from typing import Callable, TypeVar

from .classes.enums import EasingType

__all__ = [
    "EaseFunctions",
    "clamp",
    "linear_map",
    "get_ease_function",
    "interpolate",
    "parse_length",
    "parse_decibel",
    "parse_frequency",
    "parse_time",
]

T = TypeVar("T", int, float, Real, Decimal)
EaseFunction = Callable[[float], float]


def clamp(value: T, low_bound: T | None = None, high_bound: T | None = None) -> T:
    """
    Clamp a value to a range.

    If a bound is set to `None`, then the value will not be clamped on that side.

    :param value: The value to clamp.
    :param low_bound: The lower value to clamp to. If `None`, the low side is unbounded.
    :param high_bound: The higher value to clamp to. If `None`, the high side is unbounded.
    :returns: The clamped value.
    """
    if low_bound is not None and high_bound is not None and low_bound > high_bound:
        raise ValueError("low bound cannot be larger than high bound")
    if low_bound is not None and value < low_bound:
        return low_bound
    if high_bound is not None and value > high_bound:
        return high_bound
    return value


def linear_map(value: float, *, domain: tuple[float, float] = (0, 1), range: tuple[float, float] = (0, 1)) -> float:
    """
    Linearly map an interval into another interval.

    :param value: The input value. This is assumed to be within the ``domain`` interval.
    :param domain: The origin range.
    :param range: The target range.
    :returns: The resulting value after translating and scaling the origin range to match the target range.
    """
    dl, dh = domain
    rl, rh = range
    return (value - dl) / (dh - dl) * (rh - rl) + rl


class EaseFunctions(ABC):
    """A container class for easing functions that maps [0, 1] to [0, 1]. Functions should be strictly increasing."""

    @classmethod
    def linear(cls, x: float) -> float:
        """A linear map. Effectively the identity function."""
        x = clamp(x, 0, 1)
        return x

    @classmethod
    def ease_in_sin(cls, x: float) -> float:
        """An ease-in map. Uses the sine curve."""
        x = clamp(x, 0, 1)
        return sin(x * pi / 2)

    @classmethod
    def ease_out_sin(cls, x: float) -> float:
        """An ease-out map. Uses the sine curve."""
        x = clamp(x, 0, 1)
        return sin((x - 1) * pi / 2) + 1


def get_ease_function(ease_type: EasingType) -> EaseFunction:
    """Return the ease function corresponding to the enumeration member."""
    match ease_type:
        case EasingType.LINEAR:
            return EaseFunctions.linear
        case EasingType.EASE_IN_SINE:
            return EaseFunctions.ease_in_sin
        case EasingType.EASE_OUT_SINE:
            return EaseFunctions.ease_out_sin

    raise ValueError(f"invalid ease type (got {ease_type})")


def interpolate(
    ease_func: EaseFunction,
    value: Fraction,
    initial_value: Fraction,
    final_value: Fraction,
    curve_range: tuple[float, float] = (0.0, 1.0),
) -> Fraction:
    """
    Interpolates a point between two points using a given curve.

    :param ease_func: The interpolation function. Must be a function that maps [0, 1] to [0, 1]
    :param value: A value in [0.0, 1.0] at which the interpolation function is evaluated.
    :param initial_value: The initial value of the curve.
    :param final_value: The final value of the curve.
    :param curve_range: The range (effectively in percentage) at which the curve is trimmed. e.g., setting this
        parameter to (0.0, 0.5) causes this function to only use the first 50% of the curve.
    :returns: The interpolated value, which is in the interval [``initial_value``, ``final_value``].
    """
    if value <= 0:
        return initial_value
    elif value >= 1:
        return final_value

    lb, lt = curve_range

    in_val = linear_map(float(value), range=curve_range)
    mid_val = ease_func(in_val)
    out_val = linear_map(mid_val, domain=(ease_func(lb), ease_func(lt)))

    difference = final_value - initial_value
    return initial_value + Fraction(out_val) * difference


def parse_length(s: str) -> float:
    """Parse a string describing a KSH-spec length."""
    try:
        return float(s)
    except ValueError as e:
        if "/" in s:
            num, denom = s.split("/")
            return float(num) / float(denom)
        elif s.endswith("%"):
            return float(s[:-1]) / 100
        elif s.endswith("s"):
            raise ValueError(f"s/ms units are not supported (got {s})") from e
        raise ValueError(f"invalid format (got {s})") from e


def parse_decibel(s: str) -> float:
    """Parse a string describing a KSH-spec decibel."""
    if not s.endswith("dB"):
        raise ValueError(f"{s} is not a valid decibel value")
    else:
        return float(s[:-2])


def parse_frequency(s: str) -> float:
    """Parse a string describing a KSH-spec frequency."""
    if not s.endswith("Hz"):
        raise ValueError(f"{s} is not a valid frequency value")
    else:
        s = s[:-2]
        if s.endswith("k"):
            return float(s[:-1]) * 1000
        return float(s)


def parse_time(s: str) -> float:
    """Parse a string describing a KSH-spec duration."""
    if not s.endswith("s"):
        raise ValueError(f"{s} is not a valid time value")
    else:
        s = s[:-1]
        if s.endswith("m"):
            return float(s[:-1])
        return float(s) * 1000
