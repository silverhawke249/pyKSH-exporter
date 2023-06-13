import warnings
import re

from argparse import ArgumentParser
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, IntEnum, auto

from ksh2vox.classes.base import TimePoint, TimeSignature, ParserWarning


class ParserState(IntEnum):
    Nothing   = auto()
    OtherInfo = auto()
    BeatInfo  = auto()
    BPMInfo   = auto()
    TrackInfo = auto()


class ButtonType(IntEnum):
    L = 2
    A = 3
    B = 4
    C = 5
    D = 6
    R = 7

BUTTON_MAPPER = {
    '2': ButtonType.L,
    '3': ButtonType.A,
    '4': ButtonType.B,
    '5': ButtonType.C,
    '6': ButtonType.D,
    '7': ButtonType.R,
}


@dataclass
class VOXInfo():
    timesigs: dict[TimePoint, TimeSignature]          = field(default_factory=dict)
    bpms    : dict[TimePoint, Decimal]                = field(default_factory=dict)
    buttons : dict[tuple[TimePoint, ButtonType], int] = field(default_factory=dict)
    # lasers  : dict[TimePoint, int]


class Main():
    vox_data: VOXInfo = VOXInfo()

    parser_state: ParserState

    cur_bpm    : Decimal
    cur_timesig: TimeSignature

    def __init__(self, infile: str):
        self.vox_data     = VOXInfo()
        self.parser_state = ParserState.Nothing
        self.cur_bpm      = Decimal(120)
        self.cur_timesig  = TimeSignature()

        with open(infile, 'r') as f:
            for line in f:
                line = line.strip()
                if line == '#BEAT INFO':
                    self.parser_state = ParserState.BeatInfo
                elif line == '#BPM INFO':
                    self.parser_state = ParserState.BPMInfo
                elif line.startswith('#TRACK') and len(line) == 7:
                    self.parser_state = ParserState.TrackInfo
                elif line == '#END':
                    self.parser_state = ParserState.Nothing
                elif line.startswith('#'):
                    self.parser_state = ParserState.OtherInfo
                else:
                    try:
                        self.handle_line(line)
                    except ValueError:
                        warnings.warn(f'invalid line (got {line})', ParserWarning)

    def str_to_timepoint(self, time_str: str) -> TimePoint:
        return TimePoint(0, 0, 1)

    def handle_line(self, line):
        line_parts = re.split(r'\s+', line)
        if len(line_parts) < 2:
            warnings.warn(f'invalid line (got {line})', ParserWarning)
            return

        time_str, *data = line_parts
        timepoint = self.str_to_timepoint(time_str)
        if self.parser_state == ParserState.BeatInfo:
            self.cur_timesig = TimeSignature(int(data[0]), int(data[1]))
            self.vox_data.timesigs[timepoint] = self.cur_timesig
        elif self.parser_state == ParserState.BPMInfo:
            self.cur_bpm = Decimal(data[0])
            self.vox_data.bpms[timepoint] = self.cur_bpm
        elif self.parser_state == ParserState.TrackInfo:
            if line[-1] in ['1', '8']:
                pass
            elif '1' < line[-1] < '8':
                self.vox_data.buttons[timepoint, BUTTON_MAPPER[line[-1]]] = int(data[0])
            else:
                warnings.warn(f'invalid track section (got {line})', ParserWarning)
        else:
            pass


if __name__ == '__main__':
    parser = ArgumentParser(description='Predict the notecount breakdown for a given VOX file.')
    parser.add_argument('infile', help='input VOX file')

    args = parser.parse_args()
    main(args.infile)
