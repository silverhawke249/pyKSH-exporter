import dataclasses
import logging
import re

from decimal import Decimal
from itertools import pairwise
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from ..classes.base import (
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
    EasingType,
    FilterIndex,
    SegmentFlag,
    SpinType,
    VOXSection,
)

SECTION_MAP: dict[str, VOXSection] = {
    "END": VOXSection.NONE,
    "FORMAT VERSION": VOXSection.VERSION,
    "BEAT INFO": VOXSection.TIME_SIGNATURE,
    "BPM INFO": VOXSection.BPM,
    "TILT MODE INFO": VOXSection.TILT,
    "LYRIC INFO": VOXSection.LYRICS,
    "END POSITION": VOXSection.END_POSITION,
    "TAB EFFECT INFO": VOXSection.FILTER_PARAMS,
    "FXBUTTON EFFECT INFO": VOXSection.EFFECT_PARAMS,
    "TAB PARAM ASSIGN INFO": VOXSection.AUTOTAB_PARAMS,
    "REVERB EFFECT PARAM": VOXSection.REVERB,
    "TRACK1": VOXSection.TRACK_VOL_L,
    "TRACK2": VOXSection.TRACK_FX_L,
    "TRACK3": VOXSection.TRACK_BT_A,
    "TRACK4": VOXSection.TRACK_BT_B,
    "TRACK5": VOXSection.TRACK_BT_C,
    "TRACK6": VOXSection.TRACK_BT_D,
    "TRACK7": VOXSection.TRACK_FX_R,
    "TRACK8": VOXSection.TRACK_VOL_R,
    "TRACK AUTO TAB": VOXSection.AUTOTAB_SETTING,
    "TRACK ORIGINAL L": VOXSection.TRACK_VOL_L_ORIG,
    "TRACK ORIGINAL R": VOXSection.TRACK_VOL_R_ORIG,
    "SPCONTROLER": VOXSection.SPCONTROLLER,
    "SCRIPT_DEFINE": VOXSection.SCRIPT,
    "SCRIPTED_TRACK1": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK2": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK3": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK4": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK5": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK6": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK7": VOXSection.SCRIPTED_TRACK,
    "SCRIPTED_TRACK8": VOXSection.SCRIPTED_TRACK,
}
# fmt: off
SECTION_REGEX: dict[VOXSection, re.Pattern] = {
    VOXSection.NONE            : re.compile(r"(?!)"),
    VOXSection.VERSION         : re.compile(r"(?P<version>\d+)"),
    VOXSection.TIME_SIGNATURE  : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<upper>\d+)\s+(?P<lower>\d+)"),
    VOXSection.BPM             : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<bpm>\d+\.\d+)\s+(?P<unknown>\d+-?)"),
    VOXSection.TILT            : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<tilt_type>\d))?"),
    VOXSection.LYRICS          : re.compile(r"(?!)"),
    VOXSection.END_POSITION    : re.compile(r"(?P<timepoint>\d+,\d+,\d+)"),
    VOXSection.FILTER_PARAMS   : re.compile(r"(?P<filter_index>\d+)(?P<content>(,\s+\d+(\.\d+)?))+"),
    VOXSection.EFFECT_PARAMS   : re.compile(r"(?P<effect_index>\d+)(?P<content>(,\s+\d+(\.\d+)?))+"),
    VOXSection.AUTOTAB_PARAMS  : re.compile(r"(?P<index>\d+),\s+(?P<param_index>\d+),\s+"
                                            r"(?P<param_start>\d+(\.\d+)?),\s+(?P<param_end>\d+(\.\d+)?)"),
    VOXSection.REVERB          : re.compile(r"(?!)"),
    VOXSection.TRACK_VOL_L     : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<position>\d+(?:\.\d+)?)\s+"
                                            r"(?P<segment_type>\d)\s+(?P<spin_type>\d)\s+(?P<filter_type>\d)(?:\s+"
                                            r"(?P<wide_laser>\d)\s+0\s+(?P<ease_type>\d)\s+(?P<spin_length>\d+))?"),
    VOXSection.TRACK_FX_L      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<special>\d+))?"),
    VOXSection.TRACK_BT_A      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<unknown>\d+))?"),
    VOXSection.TRACK_BT_B      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<unknown>\d+))?"),
    VOXSection.TRACK_BT_C      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<unknown>\d+))?"),
    VOXSection.TRACK_BT_D      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<unknown>\d+))?"),
    VOXSection.TRACK_FX_R      : re.compile(r"(?P<timepoint>\d+,\d+,\d+)(\s+(?P<duration>\d+))?(\s+(?P<special>\d+))?"),
    VOXSection.TRACK_VOL_R     : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<position>\d+(?:\.\d+)?)\s+"
                                            r"(?P<segment_type>\d)\s+(?P<spin_type>\d)\s+(?P<filter_type>\d)(?:\s+"
                                            r"(?P<wide_laser>\d)\s+0\s+(?P<ease_type>\d)\s+(?P<spin_length>\d+))?"),
    VOXSection.AUTOTAB_SETTING : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<duration>\d+)\s+(?P<which>\d+)"),
    VOXSection.TRACK_VOL_L_ORIG: re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<position>\d+(?:\.\d+)?)\s+"
                                            r"(?P<segment_type>\d)\s+(?P<spin_type>\d)\s+(?P<filter_type>\d)(?:\s+"
                                            r"(?P<wide_laser>\d)\s+0\s+(?P<ease_type>\d)\s+(?P<spin_length>\d+))?"),
    VOXSection.TRACK_VOL_R_ORIG: re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+((?P<position>\d+(?:\.\d+)?)\s+"
                                            r"(?P<segment_type>\d)\s+(?P<spin_type>\d)\s+(?P<filter_type>\d)(?:\s+"
                                            r"(?P<wide_laser>\d)\s+0\s+(?P<ease_type>\d)\s+(?P<spin_length>\d+))?)|"
                                            r"((\s+(?P<duration>\d+))?(\s+(?P<special>\d+))?)"),
    VOXSection.SPCONTROLLER    : re.compile(r"(?P<timepoint>\d+,\d+,\d+)\s+(?P<sp_type>\w+)"
                                            r"(?P<content>(\s+-?\d+(\.\d+)?)+)"),
    VOXSection.SCRIPT          : re.compile(r".*"),
    VOXSection.SCRIPTED_TRACK  : re.compile(r".*"),
}
# fmt: on
SEGMENT_TYPE_MAP = [
    SegmentFlag.MIDDLE,
    SegmentFlag.POINT,
    SegmentFlag.START,
    SegmentFlag.END,
]
WHITESPACE_REGEX = re.compile(r"\s+")
LASER_SCALE_DEFAULT = Fraction(1)
LASER_SCALE_OLD = Fraction(1, 127)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(eq=False)
class VOXParser:
    # Init variables
    file: dataclasses.InitVar[TextIO]

    # Private variables
    _vox_path: Path = dataclasses.field(init=False)

    _current_section: VOXSection = dataclasses.field(default=VOXSection.NONE, init=False)
    _vox_version: int = dataclasses.field(default=0, init=False)
    _laser_scale: Fraction = dataclasses.field(default=LASER_SCALE_DEFAULT, init=False)

    _chart_info: ChartInfo = dataclasses.field(init=False)

    def __post_init__(self, file: TextIO):
        self._chart_info = ChartInfo()
        del self._chart_info.spcontroller_data.zoom_bottom[TimePoint()]
        del self._chart_info.spcontroller_data.zoom_top[TimePoint()]

        self._vox_path = Path(file.name).resolve()

        for lineno, line in enumerate(file):
            # Remove comments
            if "//" in line:
                index = line.find("//")
                line = line[:index]
            # Remove whitespace from the end
            line = line.rstrip()
            # Section markers start with '#'
            if line.startswith("#"):
                self._current_section = SECTION_MAP[line[1:]]
            # Content
            else:
                # Ignore everything between sections
                if self._current_section == VOXSection.NONE:
                    continue
                # Ignore empty lines
                if not line:
                    continue
                # Parse lines
                try:
                    self._parse_line(line)
                except ValueError:
                    logger.warning(f'unrecognized line at line {lineno + 1}: "{line}"')

        self._post_process()

    def _convert_vox_timepoint(self, s: str) -> TimePoint:
        # This assumes there is no need to normalize the timepoint
        m, c, d = map(int, s.split(",", maxsplit=3))
        timesig = self.chart_info.get_timesig(m)
        position = Fraction(c - 1, timesig.lower) + Fraction(d, 192)
        t = TimePoint(m, position.numerator, position.denominator)
        return t

    def _parse_line(self, line: str) -> None:
        # Ignore invalid lines
        match = SECTION_REGEX[self._current_section].match(line)
        if not match:
            raise ValueError

        if self._current_section == VOXSection.VERSION:
            self._vox_version = int(match["version"])
            if self._vox_version <= 12:
                self._laser_scale = LASER_SCALE_OLD
        elif self._current_section == VOXSection.TIME_SIGNATURE:
            timepoint = match["timepoint"]
            upper = int(match["upper"])
            lower = int(match["lower"])
            # Not gonna bother checking multiple measure overflow
            m, c, d = map(int, timepoint.split(",", maxsplit=3))
            if (c, d) != (1, 0):
                m += 1
            self.chart_info.timesigs[TimePoint(m, 0, 1)] = TimeSignature(upper, lower)
        elif self._current_section == VOXSection.BPM:
            timepoint = self._convert_vox_timepoint(match["timepoint"])
            bpm = Decimal(match["bpm"])
            # Ignoring stops because it's unnecessary (for now)
            self.chart_info.bpms[timepoint] = bpm
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
        elif self._current_section in [VOXSection.TRACK_VOL_L, VOXSection.TRACK_VOL_R]:
            # Parse all parameters
            timepoint = self._convert_vox_timepoint(match["timepoint"])
            position = Fraction(match["position"]) * self._laser_scale
            segment_type_str = match["segment_type"]
            segment_type = (
                SegmentFlag.START
                if segment_type_str == "1"
                else SegmentFlag.END
                if segment_type_str == "2"
                else SegmentFlag.MIDDLE
            )
            spin_type_str = match["spin_type"]
            spin_type = SpinType(int(spin_type_str)) if "1" <= spin_type_str <= "5" else SpinType.NO_SPIN
            filter_type_str = match["filter_type"]
            filter_type = FilterIndex(int(filter_type_str)) if "0" <= filter_type_str <= "6" else FilterIndex.CUSTOM
            wide_laser = match["wide_laser"] == "2"
            ease_type_str = match["ease_type"] or "0"
            ease_type = (
                EasingType.LINEAR
                if ease_type_str == "2"
                else EasingType.EASE_IN_SINE
                if ease_type_str == "4"
                else EasingType.EASE_OUT_SINE
                if ease_type_str == "5"
                else EasingType.NO_EASING
            )
            spin_length = int(match["spin_length"] or 0)
            # Insert into the right dictionary
            vol_dict: dict[TimePoint, VolInfo]
            if self._current_section == VOXSection.TRACK_VOL_L:
                vol_dict = self.chart_info.note_data.vol_l
            else:
                vol_dict = self.chart_info.note_data.vol_r
            # Become slam if timepoint already exists
            if timepoint in vol_dict:
                vol_dict[timepoint].point_type |= segment_type
                vol_dict[timepoint].end = position
            else:
                vol_dict[timepoint] = VolInfo(
                    position, position, spin_type, spin_length, ease_type, filter_type, segment_type, wide_laser
                )
        elif self._current_section in [VOXSection.TRACK_FX_L, VOXSection.TRACK_FX_R]:
            timepoint = self._convert_vox_timepoint(match["timepoint"])
            duration = int(match["duration"] or 0)
            special = int(match["special"] or 0)
            fx_dict: dict[TimePoint, FXInfo]
            if self._current_section == VOXSection.TRACK_FX_L:
                fx_dict = self.chart_info.note_data.fx_l
            else:
                fx_dict = self.chart_info.note_data.fx_r
            fx_dict[timepoint] = FXInfo(Fraction(duration, 192), special)
        elif self._current_section in [
            VOXSection.TRACK_BT_A,
            VOXSection.TRACK_BT_B,
            VOXSection.TRACK_BT_C,
            VOXSection.TRACK_BT_D,
        ]:
            timepoint = self._convert_vox_timepoint(match["timepoint"])
            duration = int(match["duration"] or 0)
            bt_dict: dict[TimePoint, BTInfo]
            if self._current_section == VOXSection.TRACK_BT_A:
                bt_dict = self.chart_info.note_data.bt_a
            elif self._current_section == VOXSection.TRACK_BT_B:
                bt_dict = self.chart_info.note_data.bt_b
            elif self._current_section == VOXSection.TRACK_BT_C:
                bt_dict = self.chart_info.note_data.bt_c
            else:
                bt_dict = self.chart_info.note_data.bt_d
            bt_dict[timepoint] = BTInfo(Fraction(duration, 192))
        elif self._current_section == VOXSection.AUTOTAB_SETTING:
            pass
        elif self._current_section in [VOXSection.TRACK_VOL_L_ORIG, VOXSection.TRACK_VOL_R_ORIG]:
            pass
        elif self._current_section == VOXSection.SPCONTROLLER:
            timepoint = self._convert_vox_timepoint(match["timepoint"])
            sp_type = match["sp_type"]
            content = WHITESPACE_REGEX.split(match["content"].strip())
            _, duration_str, init_val_str, end_val_str, segment_type_str, *_ = content
            duration = int(duration_str)
            init_val = Decimal(init_val_str)
            end_val = Decimal(end_val_str)
            sp_dict: dict[TimePoint, SPControllerInfo]
            if sp_type == "CAM_RotX":
                sp_dict = self.chart_info.spcontroller_data.zoom_top
            elif sp_type == "CAM_Radi":
                sp_dict = self.chart_info.spcontroller_data.zoom_bottom
            elif sp_type == "Tilt":
                sp_dict = self.chart_info.spcontroller_data.tilt
            elif sp_type == "Morphing3":
                sp_dict = self.chart_info.spcontroller_data.lane_split
            else:
                return
            if duration == 0:
                sp_dict[timepoint] = SPControllerInfo(init_val, end_val, SegmentFlag.END)
            else:
                if timepoint in sp_dict:
                    sp_dict[timepoint].end = init_val
                    sp_dict[timepoint].point_type = SegmentFlag.MIDDLE
                else:
                    sp_dict[timepoint] = SPControllerInfo(init_val, init_val, SegmentFlag.MIDDLE)
                timepoint = self.chart_info.add_duration(timepoint, duration)
                sp_dict[timepoint] = SPControllerInfo(end_val, end_val, SegmentFlag.END)
        elif self._current_section == VOXSection.SCRIPT:
            pass
        elif self._current_section == VOXSection.SCRIPTED_TRACK:
            pass
        else:
            pass

    def _post_process(self) -> None:
        # Get final measure
        final_note_timept = TimePoint()
        for _, timept, _ in self.chart_info.note_data.iter_notes():
            final_note_timept = max(timept, final_note_timept)
        self.chart_info.end_measure = final_note_timept.measure + 2

        # Fix when last vol segment isn't properly indicated
        for vol_data in [self.chart_info.note_data.vol_l, self.chart_info.note_data.vol_r]:
            vol_keys = list(vol_data.keys())
            if not vol_keys:
                continue
            vol_keys.sort()

            last_timept = vol_keys[-1]
            vol_data[last_timept].point_type |= SegmentFlag.END

        # Fix zoom_top and zoom_bottom segment flags
        camera_dicts = [self.chart_info.spcontroller_data.zoom_bottom, self.chart_info.spcontroller_data.zoom_top]
        for camera_dict in camera_dicts:
            if not camera_dict:
                continue
            timept_i = min(camera_dict.keys())
            camera_dict[timept_i].point_type |= SegmentFlag.START

        # Fix the remaining SPController data segment flags
        if self.chart_info.spcontroller_data.tilt:
            timept_i = min(self.chart_info.spcontroller_data.tilt.keys())
            self.chart_info.spcontroller_data.tilt[timept_i].point_type |= SegmentFlag.START
            for timept_i, timept_f in pairwise(self.chart_info.spcontroller_data.tilt):
                data_i = self.chart_info.spcontroller_data.tilt[timept_i]
                data_f = self.chart_info.spcontroller_data.tilt[timept_f]
                if SegmentFlag.END in data_i.point_type:
                    data_f.point_type |= SegmentFlag.START

    @property
    def vox_path(self):
        return self._vox_path

    @property
    def chart_info(self):
        return self._chart_info
