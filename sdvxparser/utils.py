"""
Classes and functions that provide general utility.
"""
from abc import ABC
from decimal import Decimal
from fractions import Fraction
from functools import partial
from math import pi, sin, sqrt
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

    @classmethod
    def bezier(cls, a: float, b: float, x: float) -> float:
        """A quadratic Bezier curve, using (a, b) as midway point."""
        # A quadratic Bezier curve is defined as b(t) = P_1 + (1 - t)^2 (P_0 - P_1) + t^2 (P_2 - P_1),
        # where t is in [0, 1] and P_0, P_1, P_2 are control points. The resulting is a smooth curve starting at
        # P_0 (corresponding to t=0) and ending at P_2 (corresponding to t=1). By setting P_0 = (0, 0), P_2 = (1, 1)
        # and clamping (a, b) to [0, 1]^2, KSMv2 ensures the curve is also a self-bijection of [0, 1]. As such, if
        # we consider the time dimension as the x-axis, we would need to find the t value that yields a given x.
        # Solving the quadratic in t and requiring a non-negative value, we get t = x / (a + sqrt(a^2 + x - 2ax))
        # for any given x. To avoid issues when a = x = 0, we'll just special case it.
        x = clamp(x, 0, 1)
        if x == 0:
            return 0
        if x == 1:
            return 1

        a = clamp(a, 0, 1)
        b = clamp(b, 0, 1)
        t = x / (a + sqrt(a ** 2 + x - 2 * a * x))
        # y(t) = b + (1 - t)^2 (0 - b) + t^2 (1 - b)
        #      = b + (1 - 2t + t^2) (-b) + t^2 - bt^2
        #      = b - b + 2bt - bt^2 + t^2 - bt^2
        #      = 2bt - 2bt^2 + t^2
        #      = 2bt(1 - t) + t^2
        return clamp(2 * b * t * (1 - t) + t ** 2, 0, 1)


def get_ease_function(ease_type: EasingType, **kwargs) -> EaseFunction:
    """Return the ease function corresponding to the enumeration member."""
    match ease_type:
        case EasingType.LINEAR:
            return EaseFunctions.linear
        case EasingType.EASE_IN_SINE:
            return EaseFunctions.ease_in_sin
        case EasingType.EASE_OUT_SINE:
            return EaseFunctions.ease_out_sin
        case EasingType.BEZIER:
            return partial(EaseFunctions.bezier, kwargs["a"], kwargs["b"])

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


def parse_time(s: str, b: str | None = None) -> float:
    """Parse a string describing a KSH-spec duration."""
    if s.endswith("s"):
        s = s[:-1]
        if s.endswith("m"):
            return float(s[:-1])
        return float(s) * 1000
    elif "/" in s:
        if b is None:
            raise ValueError(f"cannot convert {s} as time duration -- bpm not specified")
        num, denom = s.split("/")
        bpm = float(b)
        return 60 * 1000 / bpm * 4 * float(num) / float(denom)
    raise ValueError(f"{s} is not a valid time value")


def dedent(s: str) -> str:
    """Remove leading whitespaces from every line, and trim to first non-empty line."""
    return "\n".join(ss.lstrip() for ss in s.lstrip().split("\n"))
