# Sleep Sense 3

Sleep Sense 3 is a PyQt5-based sleep monitoring dashboard for loading PSG-style data, plotting physiological signals, and running apnea event detection on uploaded files.

## What This Project Does

- Loads raw CSV/TXT sleep data into the dashboard
- Displays signals such as airflow, SpO2, pulse, snoring, thorax, abdomen, body movement, and body position
- Runs rule-based apnea detection automatically after upload
- Shows detected events in the patient/event panels and lets you jump to the first event

## Main Entry Points

- `main.py` launches the main dashboard application
- `src/components/dashboard.py` contains the main dashboard UI logic
- `src/components/sleep_monitor_chart.py` contains the main chart widget and upload-to-detection flow

## Quick Start

1. Install dependencies from `requirements.txt`
2. Run the app with `python3 main.py`
3. Upload a CSV or TXT file from the dashboard
4. The app loads the data, runs rule-based detection, and jumps to the first detected event if one exists

## Upload Flow

When you upload a file, the current flow is:

1. The UI file picker opens
2. The selected file is passed into `load_psg_data_and_detect(...)`
3. The chart loads the raw PSG data
4. The rule detector runs across the full dataset
5. Detected events are emitted back to the UI
6. The chart focuses on the first detected event

The helper that centralizes this behavior lives in `src/components/sleep_monitor_chart.py`.

## Rule-Based Detection Logic

The active detector is `ai_models/sleep_apnea/detect_apnea_from_airflow.py`.

### Detection Pipeline

1. Load the raw file with `load_sleep_csv(...)`
2. Preprocess and smooth the signals
3. Build hourly airflow baselines after skipping the first 20 minutes
4. Compute a rolling airflow peak envelope
5. Calculate drop percentage with:

```text
drop_percent = ((baseline - peak_envelope) / baseline) * 100
```

6. Scan the timeline for candidate segments
7. Classify each segment into a rule label
8. Merge overlapping same-label segments
9. Return the final events list to the UI

### Label Rules

The current subtype logic is based on airflow drop percentage:

- `HSA`: `30% <= drop < 70%`
- `OSA`: `70% <= drop <= 80%`
- `CSA`: `80% < drop <= 90%`

Anything outside those ranges becomes `NO_EVENT` during final classification.

### Additional Filters

An event must also satisfy these checks during candidate generation:

- airflow minimum is low enough
- airflow drop threshold is met
- low-airflow fraction is high enough
- SpO2 drop passes the threshold

The detector also ignores events longer than the configured max duration and skips the early baseline period.

## Data Format

The loader expects headerless numeric SleepSense-style rows.

Expected columns:

- column `0`: timestamp
- column `1`: body position
- column `2`: pulse
- column `3`: SpO2
- column `4`: body movement
- column `5`: airflow
- column `7`: snoring
- column `10`: abdomen

Important notes:

- The project derives `time_sec` from sample index at a fixed `10 Hz`
- TXT files must still be numeric and parseable by `pandas.read_csv(...)`
- If the file is tab-separated or not in the expected raw layout, detection can return zero events

## UI Behavior

- `src/components/patient_info_widget.py` handles upload and event panel updates
- `src/components/dashboard.py` wires the chart to the patient panel

## AI / Legacy Notes

- The current upload flow uses rule-only detection with `enable_ai=False`
- Unused CNN, KNN, and ViT training/prediction code and model artifacts have been removed
- `ai_models/sleep_apnea/hybrid_pipeline_common.py` remains because the active rule detector imports its shared loading and preprocessing helpers

## Common Reasons For Zero Events

- The file is not in the expected raw column layout
- The TXT/CSV separator is wrong for the parser
- The signal does not contain enough valid data
- The early skip window removes the only interesting part of the recording
- The airflow drop and SpO2 thresholds are not met

## Useful Files

- `src/components/sleep_monitor_chart.py`
- `ai_models/sleep_apnea/detect_apnea_from_airflow.py`
- `ai_models/sleep_apnea/hybrid_pipeline_common.py`
- `src/components/patient_info_widget.py`
- `src/components/dashboard.py`

## License

See `LICENSE`.
