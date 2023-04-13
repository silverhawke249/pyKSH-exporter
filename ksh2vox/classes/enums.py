from enum import Enum


# TODO: Figure this out later lol
class GameBackground(Enum):
    WHAT = 0


class InfVer(Enum):
    INFINITE = 2
    GRAVITY  = 3
    HEAVENLY = 4
    VIVID    = 5
    EXCEED   = 6


class DifficultySlot(Enum):
    NOVICE   = 1
    ADVANCED = 2
    EXHAUST  = 3
    INFINITE = 4
    MAXIMUM  = 5


class SpinType(Enum):
    NO_SPIN = 0
    SINGLE_SPIN = 1
    TRIPLE_SPIN = 4
    HALF_SPIN = 5


class EasingType(Enum):
    NO_EASING = 0
    LINEAR = 2
    EASE_IN_SINE = 4
    EASE_OUT_SINE = 5


class TiltType(Enum):
    NORMAL = 0
    BIGGER = 1
    KEEP = 2


class FilterIndex(Enum):
    PEAK     = 0
    LPF      = 2
    HPF      = 4
    BITCRUSH = 5
    CUSTOM   = 6
