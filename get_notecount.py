import warnings
import re

from argparse import ArgumentParser
from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntEnum, auto
from fractions import Fraction

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


class LaserType(IntEnum):
    L = 1
    R = 8

TRACK_MAP = {
    '1': LaserType.L,
    '2': ButtonType.L,
    '3': ButtonType.A,
    '4': ButtonType.B,
    '5': ButtonType.C,
    '6': ButtonType.D,
    '7': ButtonType.R,
    '8': LaserType.R,
}


@dataclass
class VOXInfo():
    timesigs: dict[TimePoint, TimeSignature]          = field(default_factory=dict)
    bpms    : dict[TimePoint, Decimal]                = field(default_factory=dict)
    buttons : dict[tuple[TimePoint, ButtonType], int] = field(default_factory=dict)
    lasers  : set[tuple[LaserType, TimePoint]]        = field(default_factory=set)
    slams   : set[tuple[LaserType, TimePoint]]        = field(default_factory=set)


class Parser():
    vox_data    : VOXInfo
    parser_state: ParserState
    cur_bpm     : Decimal
    cur_timesig : TimeSignature

    chip_count : int
    long_count : int
    laser_count: int
    max_exscore: int

    def __init__(self, infile: str):
        self.vox_data     = VOXInfo()
        self.parser_state = ParserState.Nothing
        self.cur_bpm      = Decimal(120)
        self.cur_timesig  = TimeSignature()

        self.chip_count = 0
        self.long_count = 0
        self.laser_count = 0
        self.max_exscore = 0

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

        if (sum(s[0] == LaserType.L for s in self.vox_data.lasers) % 2 or
            sum(s[0] == LaserType.R for s in self.vox_data.lasers) % 2):
            warnings.warn(f'malformed VOX file', ParserWarning)

        self.calculate_notes()

    def str_to_timepoint(self, time_str: str) -> TimePoint:
        mno, bno, sno = [int(s) for s in time_str.split(',')]

        duration = Fraction(bno - 1, self.cur_timesig.lower)
        duration += Fraction(sno, 192 // self.cur_timesig.lower)

        return TimePoint(mno, duration.numerator, duration.denominator)

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
                # Handle start/endpoints of lasers
                if data[1] in ['1', '2']:
                    self.vox_data.lasers.add(timepoint)
                # TODO: Handle slams
            elif '1' < line[-1] < '8':
                self.vox_data.buttons[timepoint, TRACK_MAP[line[-1]]] = int(data[0])
            else:
                warnings.warn(f'invalid track section (got {line})', ParserWarning)
        else:
            pass

    def calculate_notes(self):
        for key, duration in self.vox_data.buttons.items():
            # Chip notes
            if duration == 0:
                self.chip_count += 1
                continue
            # Long notes
            timepoint, _ = key
        # TODO: Lasers

        self.max_exscore = 5 * self.chip_count + 2 * (self.long_count + self.laser_count)

if __name__ == '__main__':
    parser = ArgumentParser(description='Predict the notecount breakdown for a given VOX file.')
    parser.add_argument('infile', help='input VOX file')
    # TODO: add formatting argument

    args = parser.parse_args()
    file_parser = Parser(args.infile)

    print(f'input: {args.infile}')
    print(f'chip notes:  {file_parser.chip_count:6}')
    print(f'long notes:  {file_parser.long_count:6}')
    print(f'laser notes: {file_parser.laser_count:6}')
    print(f'max exscore: {file_parser.max_exscore:6}')
