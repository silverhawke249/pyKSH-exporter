from argparse import ArgumentParser
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, IntEnum, auto

from ksh2vox.classes.base import TimePoint, TimeSignature


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


@dataclass
class VOXInfo():
    time_sigs: dict[TimePoint, TimeSignature]
    bpms     : dict[TimePoint, Decimal]
    chips    : dict[tuple[TimePoint, ButtonType], int]
    longs    : dict[tuple[TimePoint, ButtonType], int]
    # lasers   : dict[TimePoint, int]


def main(infile: str):
    with open(infile, 'r') as f:
        parser_state = ParserState.Nothing
        for line in f:
            line = line.strip()
            if line == '#BEAT INFO':
                parser_state = ParserState.BeatInfo
            elif line == '#BPM INFO':
                parser_state = ParserState.BPMInfo
            elif line.startswith('#TRACK') and len(line) == 7:
                parser_state = ParserState.TrackInfo
            elif line == '#END':
                parser_state = ParserState.Nothing
            elif line.startswith('#'):
                parser_state = ParserState.OtherInfo
            else:
                pass



if __name__ == '__main__':
    parser = ArgumentParser(description='Predict the notecount breakdown for a given VOX file.')
    parser.add_argument('infile', help='input VOX file')

    args = parser.parse_args()
    main(args.infile)
