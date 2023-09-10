# pyKSH-exporter

Convert your KSH files into VOX format, export supporting assets, all in one place!

## Features

- Convert modern KSH format (minimum version 1.60) to version 12 VOX files.
- Detect used effects, custom effect definitions, and filter definitions, and convert them accordingly.
- Handle manually set tilt values.
- Apply smooth curves described via chart comments.
- Handle FX sound samples automatically, either via file name or via comments.
- Prepare assets in the correct formats, all in one app.

## Requirements

- Python >= 3.10.10
- DearPyGui >= 1.9.0
- Tcl/Tk >= 8.6
- construct >= 2.10
- pydub >= 0.25.1
- PIL >= 9.1.0

If documentation is needed:

- sphinx >= 7.2.5
- sphinx-autoapi >= 2.1.1
- sphinx-rtd-theme >= 1.3.0

Older versions of Python 3.10 is untested, but this certainly does not run on Python 3.9.

## Usage

Simply run `main.pyw`.

Generate the documentation for advanced usage.

## Version history

- v1.3-hotfix.1 (2023/08/20)
  - Fix issue with inserting interpolated laser points due to curve commands mid-segment.
- v1.3 (2023/08/17)
  - Add preliminary calculation of notecounts, in order to calculate maximum ex score.
    - LONG and VOL calculation is known to be inaccurate for certain situations, this is a to-do.
  - Add radar calculation, most of which is based on ZR147654's code.
    - However, ONE-HAND and HAND-TRIP is calculated slightly differently, resulting in differences.
  - Multiple custom commands can now be issued in a single timepoint by delimiting them with `;`.
  - Add simple VOX parser.
  - Add helper script for calculating notecounts and radar values.
  - Emit an error in logs when encountering problematic curve sections.
  - Allow curve commands to be issued on a laser segment, not just laser endpoints.
  - Bug fixes:
    - Fixed incorrect handling with tilt sections.
    - Short laser segments in certain positions no longer converts to a slam.
    - Audio offset is no longer ignored when exporting 2DX files.
    - Hold lengths are now factored in when calculating chart end point.
    - Logs no longer displays incorrect filename when filename is changed from default.
- v1.2 (2023/05/09)
  - `applyFilter` command added.
  - Lane splits are converted.
  - XML escaping applied to certain fields.
  - Some fields are validated on XML export; failures are logged.
  - Logs are now reverse chronological.
  - Missing backgrounds added.
- v1.1 (2023/04/30)
  - Add background previews.
  - Add advanced curve commands.
  - Add loading indicator while app is working.
  - Tweak app theming.
  - Bug fixes:
    - Unused filter removal no longer removes all filters.
    - Issue warnings when curve commands are not on a volume track point.
    - KSH parsing no longer breaks when definitions use `>`.
    - Introduce exception handling during parsing so that parsing does not halt on errors.
- v1.0 (2023/04/27)
  - Initial release.

## Future additions?

Known issues:
- [ ] Autotab duration is not calculated correctly if custom filter lasts past the end of a laser segment.
  - To work around this, ensure that custom filters are changed immediately to standard filters at the end of the laser segment.

The following are features/improvements that are being considered for implementation -- some more important than others:
- [x] Convert lane splits.
- [ ] Handle custom filters with a changing parameter.
- [ ] Attempt to match custom filters with existing effects.
- [ ] Handle charts with pre-effected audio file.
- [ ] Make MS ADPCM encoding faster (currently it takes ~15 seconds for typical audio files about ~2:30 in length).
- [x] Show a preview of the selected background.
- [ ] Release a standalone binary, possibly compiled with Nuitka.
- [x] Allow custom filters to overlap with non-peak filters.
- [ ] Fix notecount (long/vol) calculation.
