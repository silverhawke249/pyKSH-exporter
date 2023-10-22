Version history
===============

* v1.4-hotfix.1 (2023/10/23)

  * Fix exception caused when the last effect definition entry is deleted.

* v1.4 (2023/09/17)

  * Implement the "Effects", "Laser effects", and "Autotab params" tabs.
  * Add `hideBars`, `addBars`, `scriptBegin`, and `scriptEnd` commands.
  * Introduce documentation for the app and the library.
  * Improved various things behind the scenes.

* v1.3-hotfix.1 (2023/08/20)

  * Fix issue with inserting interpolated laser points due to curve commands mid-segment.

* v1.3 (2023/08/17)

  * Add preliminary calculation of notecounts, in order to calculate maximum ex score.

    * LONG and VOL calculation is known to be inaccurate for certain situations, this is a to-do.

  * Add radar calculation, most of which is based on ZR147654's code.

    * However, ONE-HAND and HAND-TRIP is calculated slightly differently, resulting in differences.

  * Multiple custom commands can now be issued in a single timepoint by delimiting them with ``;``.
  * Add simple VOX parser.
  * Add helper script for calculating notecounts and radar values.
  * Emit an error in logs when encountering problematic curve sections.
  * Allow curve commands to be issued on a laser segment, not just laser endpoints.
  * Bug fixes:

    * Fixed incorrect handling with tilt sections.
    * Short laser segments in certain positions no longer converts to a slam.
    * Audio offset is no longer ignored when exporting 2DX files.
    * Hold lengths are now factored in when calculating chart end point.
    * Logs no longer displays incorrect filename when filename is changed from default.

* v1.2 (2023/05/09)

  * ``applyFilter`` command added.
  * Lane splits are converted.
  * XML escaping applied to certain fields.
  * Some fields are validated on XML export; failures are logged.
  * Logs are now reverse chronological.
  * Missing backgrounds added.

* v1.1 (2023/04/30)

  * Add background previews.
  * Add advanced curve commands.
  * Add loading indicator while app is working.
  * Tweak app theming.
  * Bug fixes:

    * Unused filter removal no longer removes all filters.
    * Issue warnings when curve commands are not on a volume track point.
    * KSH parsing no longer breaks when definitions use ``>``.
    * Introduce exception handling during parsing so that parsing does not halt on errors.

* v1.0 (2023/04/27)

  * Initial release.
