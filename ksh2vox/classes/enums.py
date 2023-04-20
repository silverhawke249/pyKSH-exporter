from enum import Enum


class GameBackground(Enum):
    BOOTH_BRIDGE                        = 0
    BOOTH_LIME_TUNNEL_SLOW              = 1
    BOOTH_SPACE_SLOW                    = 2
    BOOTH_NEON_POP_SLOW                 = 3
    BOOTH_PLANET_SLOW                   = 4
    BOOTH_LIME_TUNNEL_FAST              = 5
    BOOTH_SPACE_FAST                    = 6
    BOOTH_NEON_POP_FAST                 = 7
    BOOTH_PLANET_FAST                   = 8
    BOOTH_RED_TUNNEL_SLOW               = 9
    BOOTH_RED_TUNNEL_FAST               = 10
    INFINITE_INFECTION_BLUE_MOON_SLOW   = 11
    INFINITE_INFECTION_BLUE_MOON_MEDIUM = 12
    INFINITE_INFECTION_BLUE_MOON_FAST   = 13
    INFINITE_INFECTION_RED_MOON_SLOW    = 14
    INFINITE_INFECTION_RED_MOON_MEDIUM  = 15
    INFINITE_INFECTION_RED_MOON_FAST    = 16
    # UNUSED                            = 17
    KAC_2013_MAXIMA_SLOW                = 18
    KAC_2013_MAXIMA_FAST                = 19
    # UNUSED                            = 20
    # UNUSED                            = 21
    # UNUSED                            = 22
    # UNUSED                            = 23
    # UNUSED                            = 24
    # UNUSED                            = 25
    # UNUSED                            = 26
    SPECIAL_BEMANI_ISEKI                = 27
    # UNUSED                            = 28
    GRAVITY_WARS_STAR_SLOW              = 29
    GRAVITY_WARS_STAR_MEDIUM            = 30
    GRAVITY_WARS_STAR_FAST              = 31
    # UNUSED                            = 32
    # UNUSED                            = 33
    SPECIAL_KAC_2012_MEDLEY             = 34
    # UNUSED                            = 35
    KAC_4TH_EVERLASTING_MESSAGE         = 36
    # UNUSED                            = 37
    GRAVITY_WARS_SUMMER_DIARY           = 38
    GRAVITY_WARS_EVILEYE_WARNING        = 39
    SPECIAL_FIRESTORM                   = 40
    GRAVITY_WARS_BEACH                  = 41
    SPECIAL_MASAKARI_BLADE              = 42
    KAC_5TH_LACHRYMA_REQUIEM            = 43
    SPECIAL_GEKKOU_RANBU                = 44
    SPECIAL_REVOLVER                    = 45
    SPECIAL_SHE_IS_MY_WIFE              = 46
    APRIL_FOOLS_GRAVITY                 = 47
    SPECIAL_FLUGEL_ARPEGGIO             = 48
    SPECIAL_PRAYER                      = 49
    SPECIAL_JOMANDA                     = 50
    HEAVENLY_HAVEN_SEA                  = 51
    # UNUSED                            = 52
    KAC_6TH_HE4VEN                      = 53
    KAC_6TH_ILLNESS_LILIN               = 54
    # UNUSED                            = 55
    # UNUSED                            = 56
    HEAVENLY_HAVEN_PURPLE_TUNNEL_SLOW   = 57
    HEAVENLY_HAVEN_PURPLE_TUNNEL_FAST   = 58
    HEAVENLY_HAVEN_RAINBOW_SLOW         = 59
    HEAVENLY_HAVEN_RAINBOW_FAST         = 60
    HEAVENLY_HAVEN_SAKURA               = 61
    # UNUSED                            = 62
    HEAVENLY_HAVEN_POP                  = 63
    # UNUSED                            = 64
    OMEGA_DIMENSION_PHASE_1             = 65
    OMEGA_DIMENSION_WHITEOUT            = 66
    OMEGA_DIMENSION_FIN4LE              = 67
    OMEGA_DIMENSION_TWOTORIAL           = 68
    KAC_7TH_I                           = 69
    SPECIAL_GERBERA_FOR_FINALISTS       = 70
    OMEGA_DIMENSION_PHASE_3             = 71
    APRIL_FOOLS_HEAVENLY                = 72
    OMEGA_DIMENSION_MADE_IN_LOVE        = 73
    OMEGA_DIMENSION_XRONIER             = 74
    VIVIDWAVE_IDOL_STAGE                = 75
    VIVIDWAVE_AUTOMATION_PARADISE       = 76
    KAC_8TH_EMBRYO                      = 77
    KAC_8TH_SEASICKNESS                 = 78
    OMEGA_DIMENSION_PHASE_6             = 79
    OMEGA_DIMENSION_EGO                 = 80
    OMEGA_DIMENSION_SHOCKWAVE           = 81
    HEXA_DIVER                          = 82
    KAC_9TH_666                         = 83
    HEXA_DIVER_VVELCOME                 = 84
    EXCEED_GEAR_MEGAMIX                 = 85
    VIVIDWAVE_BEACH_NIGHT               = 86
    HEXA_DIVER_MAYHEM                   = 87
    EXCEED_GEAR_TOWER_1                 = 88
    APRIL_FOOLS_EXCEED                  = 89
    SPECIAL_REMINISCENCE                = 90
    HEXA_DIVER_PHASE_5                  = 91
    KAC_10TH_XHRONOXAPSULE              = 92
    KAC_10TH_MIXXION                    = 93
    EXCEED_GEAR_TOWER_2                 = 94
    HEXA_DIVER_BLOOMIN                  = 95
    SPECIAL_UNDERTALE_DELTARUNE         = 96
    HEXA_DIVER_IMAKIMINI                = 97
    SPECIAL_YOU_ARE_MY_BEST_RIVAL       = 98

    def __str__(self) -> str:
        name_parts = [s.capitalize() for s in self.name.split('_')]
        return ' '.join(name_parts) + f' ({self.value})'


class InfVer(Enum):
    INFINITE = 2
    GRAVITY  = 3
    HEAVENLY = 4
    VIVID    = 5
    EXCEED   = 6

    def __str__(self) -> str:
        return f'{self.name.capitalize()} ({self.value})'


class DifficultySlot(Enum):
    NOVICE   = 1
    ADVANCED = 2
    EXHAUST  = 3
    INFINITE = 4
    MAXIMUM  = 5

    def __str__(self) -> str:
        return f'{self.name.capitalize()} ({self.value})'


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


class SegmentFlag(Enum):
    MIDDLE = 0
    START  = 1
    END    = 2
    POINT  = 4
