import dataclasses
import itertools
import re
import time
import warnings

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import TextIO
from xml.sax.saxutils import escape

from ..classes import (
    effects,
    filters,
)
from ..classes.base import (
    AutoTabInfo,
    ParserWarning,
    TimePoint,
    TimeSignature,
)
from ..classes.chart import (
    BTInfo,
    ChartInfo,
    FXInfo,
    SPControllerInfo,
    VolInfo,
)
from ..classes.enums import (
    DifficultySlot,
    EasingType,
    FilterIndex,
    SegmentFlag,
    SpinType,
    TiltType,
    VOXSection,
)
from ..classes.song import (
    SongInfo,
)
from ..utils import (
    clamp,
    interpolate,
)

BAR_LINE = '--'
CHART_REGEX = re.compile(r'^[012]{4}\|[012]{2}\|[0-9A-Za-o-:]{2}(?:(@(\(|\)|<|>)|S>|S<)\d+)?')
TITLE_REGEX = re.compile(r'[^a-zA-Z0-9]+')
LASER_POSITION = [
    '05AFKPUZejo',
    '0257ACFHKMPSUXZbehjmo',
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmno',
]
INPUT_BT  = ['bt_a', 'bt_b', 'bt_c', 'bt_d']
INPUT_FX  = ['fx_l', 'fx_r']
INPUT_VOL = ['vol_l', 'vol_r']
FILTER_TYPE_MAP = {
    'peak': FilterIndex.PEAK,
    'lpf1': FilterIndex.LPF,
    'hpf1': FilterIndex.HPF,
    'bitc': FilterIndex.BITCRUSH,
}
KSH_EFFECT_MAP: dict[str, effects.Effect] = {
    'Retrigger' : effects.Retrigger(),
    'Gate'      : effects.Gate(),
    'Flanger'   : effects.Flanger(),
    'PitchShift': effects.PitchShift(),
    'BitCrusher': effects.Bitcrush(),
    'Phaser'    : effects.Flanger(mix=50, period=2, feedback=0.35, stereo_width=0, hicut_gain=8),
    'Wobble'    : effects.Wobble(),
    'TapeStop'  : effects.Tapestop(),
    'Echo'      : effects.RetriggerEx(mix=100, wavelength=4, update_period=4, feedback=0.6, amount=1, decay=0.8),
    'SideChain' : effects.Sidechain(),
}
NO_EFFECT_INDEX             = 0
KSH_SLAM_DISTANCE           = Fraction(1, 32)
INTERPOLATION_DISTANCE      = Fraction(1, 64)
SPIN_CONVERSION_RATE        = Fraction(4, 3) / 48
STOP_CONVERSION_RATE        = Fraction(1, 192)
# KSM provides "top zoom" and "bottom zoom" while SDVX actually offers camera angle
# change and distance change... basically, polar coordinates for the camera. This
# means that the mapping between KSM and SDVX isn't as clean-cut as we'd like.
ZOOM_BOTTOM_CONVERSION_RATE = Decimal(-0.006667)
ZOOM_TOP_CONVERSION_RATE    = Decimal(0.002222)
TILT_CONVERSION_RATE        = Decimal(-0.420000)
LANE_SPLIT_CONVERSION_RATE  = Decimal(0.006667)

SECTION_MAP: dict[str, VOXSection] = {
    'END'                  : VOXSection.NONE,
    'FORMAT VERSION'       : VOXSection.VERSION,
    'BEAT INFO'            : VOXSection.TIME_SIGNATURE,
    'BPM INFO'             : VOXSection.BPM,
    'TILT MODE INFO'       : VOXSection.TILT,
    'LYRIC INFO'           : VOXSection.LYRICS,
    'END POSITION'         : VOXSection.END_POSITION,
    'TAB EFFECT INFO'      : VOXSection.FILTER_PARAMS,
    'FXBUTTON EFFECT INFO' : VOXSection.EFFECT_PARAMS,
    'TAB PARAM ASSIGN INFO': VOXSection.AUTOTAB_PARAMS,
    'REVERB EFFECT PARAM'  : VOXSection.REVERB,
    'TRACK1'               : VOXSection.TRACK_VOL_L,
    'TRACK2'               : VOXSection.TRACK_FX_L,
    'TRACK3'               : VOXSection.TRACK_BT_A,
    'TRACK4'               : VOXSection.TRACK_BT_B,
    'TRACK5'               : VOXSection.TRACK_BT_C,
    'TRACK6'               : VOXSection.TRACK_BT_D,
    'TRACK7'               : VOXSection.TRACK_FX_R,
    'TRACK8'               : VOXSection.TRACK_VOL_R,
    'TRACK AUTO TAB'       : VOXSection.AUTOTAB_SETTING,
    'TRACK ORIGINAL L'     : VOXSection.TRACK_VOL_L_ORIG,
    'TRACK ORIGINAL R'     : VOXSection.TRACK_VOL_R_ORIG,
    'SPCONTROLER'          : VOXSection.SPCONTROLLER,
}
SECTION_REGEX: dict[VOXSection, re.Pattern] = {
    VOXSection.NONE            : re.compile(r'(?!)'),
    VOXSection.VERSION         : re.compile(r'(?!)'),
    VOXSection.TIME_SIGNATURE  : re.compile(r'(?!)'),
    VOXSection.BPM             : re.compile(r'(?!)'),
    VOXSection.TILT            : re.compile(r'(?!)'),
    VOXSection.LYRICS          : re.compile(r'(?!)'),
    VOXSection.END_POSITION    : re.compile(r'(?!)'),
    VOXSection.FILTER_PARAMS   : re.compile(r'(?!)'),
    VOXSection.EFFECT_PARAMS   : re.compile(r'(?!)'),
    VOXSection.AUTOTAB_PARAMS  : re.compile(r'(?!)'),
    VOXSection.REVERB          : re.compile(r'(?!)'),
    VOXSection.TRACK_VOL_L     : re.compile(r'(?!)'),
    VOXSection.TRACK_FX_L      : re.compile(r'(?!)'),
    VOXSection.TRACK_BT_A      : re.compile(r'(?!)'),
    VOXSection.TRACK_BT_B      : re.compile(r'(?!)'),
    VOXSection.TRACK_BT_C      : re.compile(r'(?!)'),
    VOXSection.TRACK_BT_D      : re.compile(r'(?!)'),
    VOXSection.TRACK_FX_R      : re.compile(r'(?!)'),
    VOXSection.TRACK_VOL_R     : re.compile(r'(?!)'),
    VOXSection.AUTOTAB_SETTING : re.compile(r'(?!)'),
    VOXSection.TRACK_VOL_L_ORIG: re.compile(r'(?!)'),
    VOXSection.TRACK_VOL_R_ORIG: re.compile(r'(?!)'),
    VOXSection.SPCONTROLLER    : re.compile(r'(?!)'),
}
WHITESPACE_REGEX = re.compile(r'\s+')


@dataclasses.dataclass
class _HoldInfo:
    start: TimePoint
    duration: Fraction = Fraction(0)


@dataclasses.dataclass
class _LastVolInfo:
    when: TimePoint
    duration: Fraction
    prev_vol: VolInfo


def convert_laser_pos(s: str) -> Fraction:
    for laser_str in LASER_POSITION:
        if s in laser_str:
            laser_pos = laser_str.index(s)
            return Fraction(laser_pos, len(laser_str) - 1)
    return Fraction()


@dataclasses.dataclass(eq=False)
class VOXParser:
    # Init variables
    file: dataclasses.InitVar[TextIO]

    # Private variables
    _vox_path: Path = dataclasses.field(init=False)

    _current_section: VOXSection = dataclasses.field(default=VOXSection.NONE, init=False)
    _vox_version: int = dataclasses.field(default=0, init=False)

    _song_info : SongInfo  = dataclasses.field(init=False)
    _chart_info: ChartInfo = dataclasses.field(init=False)

    def __post_init__(self, file: TextIO):
        self._vox_path = Path(file.name).resolve()

        for lineno, line in enumerate(file):
            # Remove comments
            if '//' in line:
                index = line.find('//')
                line = line[:index]
            # Remove whitespace from the end
            line = line.rstrip()
            # Section markers start with '#'
            if line.startswith('#'):
                self._current_section = SECTION_MAP[line[1:]]
            # Content
            else:
                # Ignore everything between sections
                if self._current_section == VOXSection.NONE:
                    continue
                # Ignore invalid lines
                if not SECTION_REGEX[self._current_section].match(line):
                    warnings.warn(f'unrecognized line at line {lineno + 1}: "{line}"')
                    continue
                # Parse valid lines
                self._parse_line(line)

    def _parse_line(self, line) -> None:
        line_chunks = WHITESPACE_REGEX.split(line)
        if self._current_section == VOXSection.VERSION:
            pass
        elif self._current_section == VOXSection.TIME_SIGNATURE:
            pass
        elif self._current_section == VOXSection.BPM:
            pass
        elif self._current_section == VOXSection.TILT:
            pass
        elif self._current_section == VOXSection.LYRICS:
            pass
        elif self._current_section == VOXSection.END_POSITION:
            pass
        elif self._current_section == VOXSection.FILTER_PARAMS:
            pass
        elif self._current_section == VOXSection.EFFECT_PARAMS:
            pass
        elif self._current_section == VOXSection.AUTOTAB_PARAMS:
            pass
        elif self._current_section == VOXSection.REVERB:
            pass
        elif self._current_section == VOXSection.TRACK_VOL_L:
            pass
        elif self._current_section == VOXSection.TRACK_FX_L:
            pass
        elif self._current_section == VOXSection.TRACK_BT_A:
            pass
        elif self._current_section == VOXSection.TRACK_BT_B:
            pass
        elif self._current_section == VOXSection.TRACK_BT_C:
            pass
        elif self._current_section == VOXSection.TRACK_BT_D:
            pass
        elif self._current_section == VOXSection.TRACK_FX_R:
            pass
        elif self._current_section == VOXSection.TRACK_VOL_R:
            pass
        elif self._current_section == VOXSection.AUTOTAB_SETTING:
            pass
        elif self._current_section == VOXSection.TRACK_VOL_L_ORIG:
            pass
        elif self._current_section == VOXSection.TRACK_VOL_R_ORIG:
            pass
        elif self._current_section == VOXSection.SPCONTROLLER:
            pass
        else:
            pass

    @property
    def vox_path(self):
        return self._vox_path

    @property
    def song_info(self):
        return self._song_info

    @property
    def chart_info(self):
        return self._chart_info
