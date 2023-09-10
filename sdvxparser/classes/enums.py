"""
General purpose enumerations.
"""
from enum import Enum, Flag, auto, unique

__all__ = [
    "GameBackground",
    "InfVer",
    "DifficultySlot",
    "SpinType",
    "EasingType",
    "TiltType",
    "FilterIndex",
    "SegmentFlag",
    "VOXSection",
    "NoteType",
]


@unique
class GameBackground(Enum):
    """Enumeration for the game backgrounds."""

    BOOTH_BRIDGE = 0
    BOOTH_LIME_TUNNEL_SLOW = 1
    BOOTH_SPACE_SLOW = 2
    BOOTH_NEON_POP_SLOW = 3
    BOOTH_PLANET_SLOW = 4
    BOOTH_LIME_TUNNEL_FAST = 5
    BOOTH_SPACE_FAST = 6
    BOOTH_NEON_POP_FAST = 7
    BOOTH_PLANET_FAST = 8
    BOOTH_RED_TUNNEL_SLOW = 9
    BOOTH_RED_TUNNEL_FAST = 10
    INFINITE_INFECTION_BLUE_MOON_SLOW = 11
    INFINITE_INFECTION_BLUE_MOON_MEDIUM = 12
    INFINITE_INFECTION_BLUE_MOON_FAST = 13
    INFINITE_INFECTION_RED_MOON_SLOW = 14
    INFINITE_INFECTION_RED_MOON_MEDIUM = 15
    INFINITE_INFECTION_RED_MOON_FAST = 16
    SPECIAL_KAC_2013_MAXIMA_SLOW = 17
    SPECIAL_KAC_2013_MAXIMA_MEDIUM = 18
    SPECIAL_KAC_2013_MAXIMA_FAST = 19
    SPECIAL_BLASTER_GATE_SLOW = 20
    SPECIAL_BLASTER_GATE_MEDIUM = 21
    SPECIAL_BLASTER_GATE_FAST = 22
    # Crashes the game!! = 23
    # Crashes the game!! = 24
    # Crashes the game!! = 25
    SPECIAL_BEMANI_ISEKI_SLOW = 26
    SPECIAL_BEMANI_ISEKI_MEDIUM = 27
    SPECIAL_BEMANI_ISEKI_FAST = 28
    GRAVITY_WARS_STAR_SLOW = 29
    GRAVITY_WARS_STAR_MEDIUM = 30
    GRAVITY_WARS_STAR_FAST = 31
    SPECIAL_KAC_2012_MEDLEY_SLOW = 32
    SPECIAL_KAC_2012_MEDLEY_MEDIUM = 33
    SPECIAL_KAC_2012_MEDLEY_FAST = 34
    SPECIAL_EVERLASTING_MESSAGE_SLOW = 35
    SPECIAL_EVERLASTING_MESSAGE_MEDIUM = 36
    SPECIAL_EVERLASTING_MESSAGE_FAST = 37
    GRAVITY_WARS_SUMMER_DIARY = 38
    GRAVITY_WARS_EVILEYE_GRACE = 39
    SPECIAL_FIRESTORM = 40
    GRAVITY_WARS_BEACH = 41
    SPECIAL_MASAKARI_BLADE = 42
    SPECIAL_LACHRYMA_REQUIEM = 43
    SPECIAL_GEKKOU_RANBU = 44
    SPECIAL_REVOLVER = 45
    SPECIAL_SHE_IS_MY_WIFE = 46
    APRIL_FOOLS_GRAVITY = 47
    SPECIAL_FLUGEL_ARPEGGIO = 48
    SPECIAL_PRAYER = 49
    SPECIAL_JOMANDA = 50
    HEAVENLY_HAVEN_SEA = 51
    HEAVENLY_HAVEN_SKY = 52
    SPECIAL_HE4VEN = 53
    SPECIAL_ILLNESS_LILIN = 54
    HEAVENLY_HAVEN_ORANGE_TUNNEL_SLOW = 55
    HEAVENLY_HAVEN_ORANGE_TUNNEL_FAST = 56
    HEAVENLY_HAVEN_PURPLE_TUNNEL_SLOW = 57
    HEAVENLY_HAVEN_PURPLE_TUNNEL_FAST = 58
    HEAVENLY_HAVEN_RAINBOW_SLOW = 59
    HEAVENLY_HAVEN_RAINBOW_FAST = 60
    HEAVENLY_HAVEN_SAKURA = 61
    HEAVENLY_HAVEN_CITY = 62
    HEAVENLY_HAVEN_POP = 63
    HEAVENLY_HAVEN_ECLIPSE = 64
    OMEGA_DIMENSION_PHASE_1 = 65
    OMEGA_DIMENSION_WHITEOUT = 66
    OMEGA_DIMENSION_FIN4LE = 67
    OMEGA_DIMENSION_TWOTORIAL = 68
    OMEGA_DIMENSION_I = 69
    SPECIAL_GERBERA_FOR_FINALISTS = 70
    OMEGA_DIMENSION_PHASE_3 = 71
    APRIL_FOOLS_HEAVENLY = 72
    OMEGA_DIMENSION_MADE_IN_LOVE = 73
    OMEGA_DIMENSION_XRONIER = 74
    VIVIDWAVE_IDOL_STAGE = 75
    VIVIDWAVE_AUTOMATION_PARADISE = 76
    OMEGA_DIMENSION_EMBRYO = 77
    OMEGA_DIMENSION_SEASICKNESS = 78
    OMEGA_DIMENSION_PHASE_6 = 79
    OMEGA_DIMENSION_EGO = 80
    OMEGA_DIMENSION_SHOCKWAVE = 81
    HEXA_DIVER_PHASE_1 = 82
    HEXA_DIVER_666 = 83
    HEXA_DIVER_VVELCOME = 84
    EXCEED_GEAR_MEGAMIX = 85
    VIVIDWAVE_BEACH_NIGHT = 86
    HEXA_DIVER_MAYHEM = 87
    EXCEED_GEAR_TOWER_1 = 88
    APRIL_FOOLS_EXCEED = 89
    SPECIAL_REMINISCENCE = 90
    HEXA_DIVER_PHASE_5 = 91
    HEXA_DIVER_XHRONOXAPSULE = 92
    HEXA_DIVER_MIXXION = 93
    EXCEED_GEAR_TOWER_2 = 94
    HEXA_DIVER_BLOOMIN = 95
    SPECIAL_UNDERTALE_DELTARUNE = 96
    HEXA_DIVER_IMAKIMINI = 97
    SPECIAL_YOU_ARE_MY_BEST_RIVAL = 98
    SPECIAL_SUDDENDEATH = 99
    EXCEED_GEAR_BEMANI_PRO_LEAGUE = 100
    EXCEED_GEAR_JAPANESQUE = 101
    HEXA_DIVER_APOCALYPSE_RAY = 102

    def __str__(self) -> str:
        name_parts = [s.capitalize() for s in self.name.split("_")]
        return " ".join(name_parts) + f" ({self.value})"


class InfVer(Enum):
    """Enumeration for the INFINITE difficulty name."""

    INFINITE = 2
    GRAVITY = 3
    HEAVENLY = 4
    VIVID = 5
    EXCEED = 6

    def __str__(self) -> str:
        return f"{self.name.capitalize()} ({self.value})"


class DifficultySlot(Enum):
    """Enumeration for the difficulty slot."""

    NOVICE = 1
    ADVANCED = 2
    EXHAUST = 3
    INFINITE = 4
    MAXIMUM = 5

    def __str__(self) -> str:
        return f"{self.name.capitalize()} ({self.value})"

    def to_shorthand(self) -> str:
        return f"{self.value}{self.name.lower()[0]}"


class SpinType(Enum):
    """Enumeration for the lane spin type occuring with laser slams."""

    NO_SPIN = 0
    SINGLE_SPIN = 1
    SINGLE_SPIN_2 = 2
    SINGLE_SPIN_3 = 3
    TRIPLE_SPIN = 4
    HALF_SPIN = 5


class EasingType(Enum):
    """Enumeration for the laser segment's easing type."""

    NO_EASING = 0
    LINEAR = 2
    EASE_IN_SINE = 4
    EASE_OUT_SINE = 5


class TiltType(Enum):
    """Enumeration for the lane tilt type."""

    NORMAL = 0
    BIGGER = 1
    KEEP = 2


class FilterIndex(Enum):
    """Enumeration for the laser's filter."""

    PEAK = 0
    LPF_ALT = 1
    LPF = 2
    HPF_ALT = 3
    HPF = 4
    BITCRUSH = 5
    CUSTOM = 6


class SegmentFlag(Flag):
    """Flag enumeration for the laser segment's segment type."""

    MIDDLE = 0
    START = 1
    END = 2
    POINT = 3


class VOXSection(Enum):
    """Enumeration for VOX file format sections."""

    NONE = 0
    VERSION = auto()
    TIME_SIGNATURE = auto()
    BPM = auto()
    TILT = auto()
    LYRICS = auto()
    END_POSITION = auto()
    FILTER_PARAMS = auto()
    EFFECT_PARAMS = auto()
    AUTOTAB_PARAMS = auto()
    REVERB = auto()
    TRACK_VOL_L = auto()
    TRACK_FX_L = auto()
    TRACK_BT_A = auto()
    TRACK_BT_B = auto()
    TRACK_BT_C = auto()
    TRACK_BT_D = auto()
    TRACK_FX_R = auto()
    TRACK_VOL_R = auto()
    AUTOTAB_SETTING = auto()
    TRACK_VOL_L_ORIG = auto()
    TRACK_VOL_R_ORIG = auto()
    SPCONTROLLER = auto()
    SCRIPT = auto()
    SCRIPTED_TRACK = auto()


class NoteType(Flag):
    """
    Flag enumeration for the note type.

    These are reversed on purpose, so that the binary representation can be read left-to-right.
    """

    VOL_R = auto()
    FX_R = auto()
    BT_D = auto()
    BT_C = auto()
    BT_B = auto()
    BT_A = auto()
    FX_L = auto()
    VOL_L = auto()
    DUMMY = auto()

    def __str__(self) -> str:
        if self.name is None:
            return super().__str__()
        return self.name.replace("_", "-")
