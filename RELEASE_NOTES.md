# Sleep Sense release notes

Use this file to identify which software release produced a report. The
software version printed on a report should match the release heading below.

## Version 3.1.1

**Changes included in this release**

- Report hypoxic-burden ensemble averaging now uses only complete 201-sample
  SpO2 windows. Edge-truncated events remain eligible for per-event burden;
  if fewer than five complete usable windows remain, the standard fallback
  window is used. This prevents the report crash caused by unequal window
  lengths without deleting edge events from the respiratory event list.
- EXE and installer version updated to `3.1.1`.

## Version 3.1.0

**Build/report identification**

- The running software version is shown in the report footer and in **Help → Info**.
- The PyInstaller build reads `version_info.txt` to embed the EXE's Windows
  product/file version. The installer version is set in `setup.iss`.
- For a report to show `3.1.0`, build and distribute the EXE after applying
  these version settings. An older EXE keeps its old embedded version.

**Changes included in this release**

- SpO₂ values above 100 are capped at 100 for display and report metrics.
- The default airflow drop required to classify an apnea as OSA/CSA/MSA is
  90%; the Analysis Parameters default and Standard parameter action use 90%.
- A brief SpO₂ zero/missing interval (up to 60 seconds) can retain the prior
  displayed value; longer intervals are treated as sensor-off by the chart.
- Manual or modified events receive a red dot in the report hypnogram.
- Help contains a running-version **Info** item; Recording Info and Device Info
  were removed from that menu.
- Sensor-off and periodicity-loss events are not inferred from effort-channel
  noise when the recording has no usable airflow channel overall.
- The 1-hour minimum restrictions for loading data and opening a report were
  removed. For recordings longer than 10 minutes, the first and last 5 minutes
  are excluded from analysis.
- The playback event heading/status badge is hidden.

## Versioning notes

- EXE product/file version: `version_info.txt`
- Source-mode version fallback: `src/utils/app_version.py`
- Installer version and output filename: `setup.iss`
- PyInstaller includes the EXE version resource through `SleepSense.spec`.

When preparing a release, update all three version values together, add a new
section here describing the changes, and rebuild the EXE/installer. Keep a copy
of this file with each distributed release so report versions can be matched
to the corresponding notes later.
