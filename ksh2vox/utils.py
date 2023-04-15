from math import pi, sin
from numbers import Real
from typing import TypeVar

from .classes import EasingType

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
        return initial_value + (sin((count / total - 1) * pi / 2) + 1) * difference
    elif ease_type == EasingType.EASE_OUT_SINE:
        return initial_value + sin(count / total * pi / 2) * difference
    else:
        raise ValueError(f'invalid ease type (got {ease_type})')
