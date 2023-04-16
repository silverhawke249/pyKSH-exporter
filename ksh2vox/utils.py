from math import pi, sin
from numbers import Real
from typing import TypeVar

from .classes.enums import EasingType

T = TypeVar('T', int, float, Real)
U = TypeVar('U', bound=Real)


def interpolate(
    ease_type: EasingType,
    count: T,
    total: T,
    initial_value: U,
    final_value: U,
) -> U:
    if count <= 0:
        return initial_value
    elif count >= total:
        return final_value

    difference = final_value - initial_value
    if ease_type == EasingType.LINEAR:
        return initial_value + count / total * difference
    elif ease_type == EasingType.EASE_IN_SINE:
        return initial_value + sin(count / total * pi / 2) * difference
    elif ease_type == EasingType.EASE_OUT_SINE:
        return initial_value + (sin((count / total - 1) * pi / 2) + 1) * difference
    else:
        raise ValueError(f'invalid ease type (got {ease_type})')


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
