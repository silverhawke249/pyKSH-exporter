from abc import ABC
from decimal import Decimal
from math import pi, sin
from numbers import Real
from typing import TypeVar

from .classes.enums import EasingType

T = TypeVar('T', int, float, Real, Decimal)
U = TypeVar('U', bound=Real)


def clamp(
    value: T,
    low_bound: T | None = None,
    high_bound: T | None = None
) -> T:
    """ Clamp a value to a range. Pass None to not clamp from that side. """
    if low_bound is not None and high_bound is not None and low_bound > high_bound:
        raise ValueError('low bound cannot be larger than high bound')
    if low_bound is not None and value < low_bound:
        return low_bound
    if high_bound is not None and value > high_bound:
        return high_bound
    return value


def linear_map(
    value: float,
    *,
    domain: tuple[float, float] = (0, 1),
    range: tuple[float, float] = (0, 1)
) -> float:
    """ Linearly map an interval into another interval. """
    dl, dh = domain
    rl, rh = range
    return (value - dl) / (dh - dl) * (rh - rl) + rl


class EaseFunctions(ABC):
    """ Provide easing functions that maps [0, 1] to [0, 1]. Functions should be strictly increasing. """
    @classmethod
    def linear(cls, x: float) -> float:
        x = clamp(x, 0, 1)
        return x

    @classmethod
    def ease_in_sin(cls, x: float) -> float:
        x = clamp(x, 0, 1)
        return sin(x * pi / 2)

    @classmethod
    def ease_out_sin(cls, x: float) -> float:
        x = clamp(x, 0, 1)
        return sin((x - 1) * pi / 2) + 1


def interpolate(
    ease_type: EasingType,
    count: U,
    total: U,
    initial_value: U,
    final_value: U,
    limit_bottom: float = 0.0,
    limit_top: float = 1.0
) -> U:
    if count <= 0:
        return initial_value
    elif count >= total:
        return final_value

    if ease_type == EasingType.LINEAR:
        func = EaseFunctions.linear
    elif ease_type == EasingType.EASE_IN_SINE:
        func = EaseFunctions.ease_in_sin
    elif ease_type == EasingType.EASE_OUT_SINE:
        func = EaseFunctions.ease_out_sin
    else:
        raise ValueError(f'invalid ease type (got {ease_type})')

    in_val = linear_map(count / total, range=(limit_bottom, limit_top))
    mid_val = func(in_val)
    out_val = linear_map(mid_val, domain=(func(limit_bottom), func(limit_top)))

    difference = final_value - initial_value
    return initial_value + out_val * difference


def parse_length(
    s: str
) -> float:
    try:
        return float(s)
    except ValueError as e:
        if '/' in s:
            num, denom = s.split('/')
            return float(num) / float(denom)
        elif s.endswith('%'):
            return float(s[:-1]) / 100
        elif s.endswith('s'):
            raise ValueError(f's/ms units are not supported (got {s})') from e
        raise ValueError(f'invalid format (got {s})') from e


def parse_decibel(
    s: str
) -> float:
    if not s.endswith('dB'):
        raise ValueError(f'{s} is not a valid decibel value')
    else:
        return float(s[:-2])


def parse_frequency(
    s: str
) -> float:
    if not s.endswith('Hz'):
        raise ValueError(f'{s} is not a valid frequency value')
    else:
        s = s[:-2]
        if s.endswith('k'):
            return float(s[:-1]) * 1000
        return float(s)


def parse_time(
    s: str
) -> float:
    if not s.endswith('s'):
        raise ValueError(f'{s} is not a valid time value')
    else:
        s = s[:-1]
        if s.endswith('m'):
            return float(s[:-1])
        return float(s) * 1000
