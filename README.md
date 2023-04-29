# pyKSH-exporter

Convert your KSH files into VOX format, export supporting assets, all in one place!

## Usage

Simply run `main.pyw`. Things are pretty self-explanatory.

## Requirements

- Python >= 3.10.10
- DearPyGui >= 1.9.0
- Tcl/Tk >= 8.6
- construct >= 2.10
- pydub >= 0.25.1
- PIL >= 9.1.0

Older versions of Python 3.10 is untested, but this certainly does not run on Python 3.9.

## Features

- Convert modern KSH format (minimum version 1.60) to version 12 VOX files.
- Detect used effects, custom effect definitions, and filter definitions, and convert them accordingly.
- Handle manually set tilt values.
- Apply smooth curves described via chart comments.
- Handle FX sound samples automatically, either via file name or via comments.
- Prepare assets in the correct formats, all in one app.

## Advanced usage

The following chart comments are treated as commands:
- `curveBeginL`, `curveBeginR`, `curveBeginLR`
- `curveEndL`, `curveEndR`, `curveEndLR`
- `lightFXL`, `lightFXR`, `lightFXLR`

### Curves

For the `curveBegin` commands, it must be followed by `=` and a number `2`, `4`, or `5`:
- `curveBeginL=4` indicates that the left volume track will have an ease-out curve.
- `curveBeginLR=2,5` indicates that the left volume track will have a linear "curve", while the right volume track will have an ease-in curve.
- `curveBeginLR=4` indicates that both volume tracks will have an ease-out curve.

The curves are calculated using a sine curve. Currently, no other curves are implemented.

For the `curveEnd` commands, nothing else is needed. Simply write `curveEndL`/`curveEndR`/`curveEndLR` as appropriate.

A curved segment may be closed with either a `curveEnd` command or more `curveBegin` commands.

If multiple commands need to be issued at the same time point, they can be separated by a semicolon (`;`) -- e.g. `curveBeginL=4;curveEndR`.

### FX chip SE

FX chip sound sample can be autodetected by using the appropriate file name (`1.wav`, etc.) or by specifying it using the `lightFX` command -- e.g. `lightFXLR=7`.

## Version history

- v1.0 (2023/04/27)
  - Initial release.

## Future additions?

The following are features/improvements that are being considered for implementation -- some more important than others:
- Convert lane splits.
- Handle custom filters with a changing parameter.
- Attempt to match custom filters with existing effects.
- Handle charts with pre-effected audio file.
- Make MS ADPCM encoding faster (currently it takes ~15 seconds for typical audio files about ~2:30 in length).
- Show a preview of the selected background.
- Release a standalone binary, possibly compiled with Nuitka.
