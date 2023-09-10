#!/usr/bin/env python
import argparse
import logging
import pathlib
import sys

from sdvxparser.parser.ksh import KSHParser
from sdvxparser.parser.vox import VOXParser


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reads a VOX/KSH file and prints out calculated notecount and radar values."
    )
    parser.add_argument("filename", nargs="+", help="input VOX/KSH file(s) to read")
    parser.add_argument("--porcelain", action="store_true", help="produce machine readable output")
    parser.add_argument("--log-level", action="store", help="change logging level. invalid values are silently ignored")
    args = parser.parse_args()

    log_level = logging.WARNING
    if args.log_level is not None:
        try:
            log_level_int = int(args.log_level)
            if log_level_int in logging._levelToName:
                log_level = log_level_int
        except ValueError:
            log_level_str = args.log_level.upper()
            log_level = logging._nameToLevel.get(log_level_str, log_level)
    logging.basicConfig(format="[%(levelname)s %(asctime)s] %(filename)s: %(message)s", level=log_level)

    for fn in args.filename:
        try:
            fpath = pathlib.Path(fn)
            FileParser: type[KSHParser | VOXParser]
            if fpath.suffix == ".ksh":
                FileParser = KSHParser
            elif fpath.suffix == ".vox":
                FileParser = VOXParser
            else:
                raise OSError("invalid file extension")

            with fpath.open("r", encoding="utf-8") as f:
                file_parser = FileParser(f)

            if args.porcelain:
                print(
                    "\t".join(
                        str(n)
                        for n in [
                            file_parser.chart_info.chip_notecount,
                            file_parser.chart_info.long_notecount,
                            file_parser.chart_info.vol_notecount,
                        ]
                    )
                )
                print(
                    "\t".join(
                        str(n)
                        for n in [
                            file_parser.chart_info.radar_notes,
                            file_parser.chart_info.radar_peak,
                            file_parser.chart_info.radar_tsumami,
                            file_parser.chart_info.radar_onehand,
                            file_parser.chart_info.radar_handtrip,
                            file_parser.chart_info.radar_tricky,
                        ]
                    )
                )
            else:
                print(fn)
                print("=====  NOTECOUNTS  =====")
                print(f"CHIP             | {file_parser.chart_info.chip_notecount:>5}")
                print(f"LONG             | {file_parser.chart_info.long_notecount:>5}")
                print(f"VOL              | {file_parser.chart_info.vol_notecount:>5}")
                print("===== RADAR VALUES =====")
                print(f"NOTES            | {file_parser.chart_info.radar_notes:>5}")
                print(f"PEAK             | {file_parser.chart_info.radar_peak:>5}")
                print(f"TSUMAMI          | {file_parser.chart_info.radar_tsumami:>5}")
                print(f"ONE-HAND         | {file_parser.chart_info.radar_onehand:>5}")
                print(f"HAND-TRIP        | {file_parser.chart_info.radar_handtrip:>5}")
                print(f"TRICKY           | {file_parser.chart_info.radar_tricky:>5}")
                print()
        except Exception as err:
            if args.porcelain:
                print("\t".join(["-1"] * 3))
                print("\t".join(["-1"] * 6))
                continue
            print(f"{parser.prog}: {type(err).__name__}: {err}")
            print(f"{parser.prog}: error: unable to parse file, or no such file: {fn!r}")
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
