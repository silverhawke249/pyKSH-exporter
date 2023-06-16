import warnings
import re

from argparse import ArgumentParser
from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntEnum, auto
from fractions import Fraction
from functools import cache

from ksh2vox.classes.base import TimeSignature, ParserWarning

Tickcount = int


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

TRACK_MAP: dict[str, LaserType | ButtonType] = {
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
    timesigs: dict[Tickcount, TimeSignature]          = field(default_factory=dict)
    bpms    : dict[Tickcount, Decimal]                = field(default_factory=dict)
    buttons : dict[tuple[Tickcount, ButtonType], int] = field(default_factory=dict)
    lasers  : dict[LaserType, list[Tickcount]]        = field(default_factory=dict)
    slams   : dict[LaserType, set[Tickcount]]         = field(default_factory=dict)

    def __post_init__(self):
        self.lasers = {
            LaserType.L: [],
            LaserType.R: [],
        }
        self.slams = {
            LaserType.L: set(),
            LaserType.R: set(),
        }


class Parser():
    vox_data    : VOXInfo
    parser_state: ParserState
    cur_bpm     : Decimal
    cur_timesig : TimeSignature
    cur_track   : str
    prev_laser  : dict[LaserType, Tickcount]

    chip_count : int
    long_count : int
    laser_count: int
    max_exscore: int

    def __init__(self, infile: str):
        self.vox_data     = VOXInfo()
        self.parser_state = ParserState.Nothing
        self.cur_bpm      = Decimal(120)
        self.cur_timesig  = TimeSignature()
        self.cur_track    = '0'
        self.prev_laser   = {
            LaserType.L: Tickcount(0),
            LaserType.R: Tickcount(0),
        }

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
                    self.cur_track    = line[-1]
                elif line == '#END':
                    self.parser_state = ParserState.Nothing
                elif line.startswith('#'):
                    self.parser_state = ParserState.OtherInfo
                else:
                    try:
                        self.handle_line(line)
                    except ValueError:
                        warnings.warn(f'invalid line (got {line})', ParserWarning)

        if (len(self.vox_data.lasers[LaserType.L]) % 2 != 0 or
            len(self.vox_data.lasers[LaserType.R]) % 2 != 0):
            warnings.warn(f'malformed VOX file', ParserWarning)

        self.calculate_notes()

    @cache
    def str_to_tick(self, time_str: str) -> Tickcount:
        mno, bno, sno = [int(s) for s in time_str.split(',')]
        if mno <= 0:
            raise ValueError(f'measure number must be positive (got {mno})')

        if (mno, bno, sno) == (1, 1, 0):
            duration = 0
        elif (bno, sno) == (1, 0):
            duration = self.str_to_tick(f'{mno - 1:03},01,00')
            timesig = self.get_active_timesig(duration)
            duration += timesig.upper * (192 // timesig.lower)
        else:
            duration = self.str_to_tick(f'{mno:03},01,00')
            timesig = self.get_active_timesig(duration)
            duration += (bno - 1) * (192 // timesig.lower) + sno

        return duration

    def get_active_bpm(self, tick: Tickcount) -> Decimal:
        prev_bpm = Decimal(0)
        for time, bpm in self.vox_data.bpms.items():
            if time > tick:
                break
            prev_bpm = bpm

        return prev_bpm

    def get_active_timesig(self, tick: Tickcount) -> TimeSignature:
        prev_timesig = TimeSignature()
        for time, timesig in self.vox_data.timesigs.items():
            if time > tick:
                break
            prev_timesig = timesig

        return prev_timesig

    def handle_line(self, line) -> None:
        if self.parser_state in [ParserState.Nothing, ParserState.OtherInfo]:
            return

        line_parts = re.split(r'\s+', line)
        if len(line_parts) < 2:
            warnings.warn(f'invalid line (got {line})', ParserWarning)
            return

        time_str, *data = line_parts
        tick = self.str_to_tick(time_str)
        if self.parser_state == ParserState.BeatInfo:
            self.cur_timesig = TimeSignature(int(data[0]), int(data[1]))
            self.vox_data.timesigs[tick] = self.cur_timesig
        elif self.parser_state == ParserState.BPMInfo:
            self.cur_bpm = Decimal(data[0])
            self.vox_data.bpms[tick] = self.cur_bpm
        elif self.parser_state == ParserState.TrackInfo:
            if self.cur_track not in TRACK_MAP:
                warnings.warn(f'invalid track section (got {self.cur_track})', ParserWarning)
                return

            track_type = TRACK_MAP[self.cur_track]
            if isinstance(track_type, LaserType):
                # Handle start/endpoints of lasers
                if data[1] != '0':
                    self.vox_data.lasers[track_type].append(tick)
                # Handle slams
                if self.prev_laser[track_type] == tick:
                    self.vox_data.slams[track_type].add(tick)
                self.prev_laser[track_type] = tick
            elif isinstance(track_type, ButtonType):
                self.vox_data.buttons[tick, track_type] = int(data[0])
            else:
                pass
        else:
            pass

    def calculate_notes(self) -> None:
        for key, duration in self.vox_data.buttons.items():
            # Chip notes
            if duration == 0:
                self.chip_count += 1
                continue
            # Long notes
            # TODO: Figure out what's wrong with this
            tick, _ = key
            cur_bpm = self.get_active_bpm(tick)
            tick_rate = 24 if cur_bpm >= 256 else 12
            remainder = 0
            if tick % tick_rate != 0:
                print(key, duration)
                remainder = tick_rate - (tick % tick_rate)
                self.long_count += 1
            # TODO: Factor in BPM changes
            self.long_count += (duration - remainder) // tick_rate
        # Lasers
        laser_ticks: dict[LaserType, list[Tickcount]] = {
            LaserType.L: [],
            LaserType.R: [],
        }
        for laser_type, laser_timepts in self.vox_data.lasers.items():
            for laser_s, laser_e in zip(*[iter(laser_timepts)] * 2):
                # Round to next tick
                cur_bpm = self.get_active_bpm(laser_s)
                tick_rate = 24 if cur_bpm >= 256 else 12
                if laser_s % tick_rate != 0:
                    remainder = tick_rate - (laser_s % tick_rate)
                    cur_timept = laser_s + remainder
                else:
                    cur_timept = laser_s
                # Add ticks until it exceeds endpoint
                # TODO: Factor in BPM changes
                while cur_timept < laser_e:
                    laser_ticks[laser_type].append(cur_timept)
                    cur_timept += tick_rate
            self.laser_count += len(laser_ticks[laser_type])
        # Slams
        slam_overlapping_ticks: dict[LaserType, list[Tickcount]] = {
            LaserType.L: [],
            LaserType.R: [],
        }
        for laser_type, slam_timepts in self.vox_data.slams.items():
            for tick in slam_timepts:
                # Round to previous tick
                cur_bpm = self.get_active_bpm(tick)
                tick_rate = 24 if cur_bpm >= 256 else 12
                if tick % tick_rate != 0:
                    tick -= tick % tick_rate
                if tick in laser_ticks[laser_type]:
                    if tick in slam_overlapping_ticks[laser_type]:
                        self.laser_count += 1
                    else:
                        slam_overlapping_ticks[laser_type].append(tick)
                else:
                    self.laser_count += 1

        self.max_exscore = 5 * self.chip_count + 2 * (self.long_count + self.laser_count)

if __name__ == '__main__':
    parser = ArgumentParser(description='Predict the notecount breakdown for a given VOX file.')
    parser.add_argument('infile', help='input VOX file')
    # TODO: Add formatting argument

    args = parser.parse_args()
    file_parser = Parser(args.infile)

    print(f'input: {args.infile}')
    print(f'chip notes : {file_parser.chip_count:6}')
    print(f'long notes : {file_parser.long_count:6}')
    print(f'laser notes: {file_parser.laser_count:6}')
    print(f'max chain  : {file_parser.chip_count + file_parser.long_count + file_parser.laser_count:6}')
    print(f'max exscore: {file_parser.max_exscore:6}')
