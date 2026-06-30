#!/usr/bin/env python3

import argparse
import json

from hybrid_pipeline_common import load_sleep_csv, preprocess_signals, detect_rule_candidates


def main():
    parser = argparse.ArgumentParser(description="Detect apnea event candidates from raw SleepSense CSV.")
    parser.add_argument("csv_path")
    parser.add_argument("--min-event-seconds", type=float, default=10.0)
    parser.add_argument("--airflow-drop-threshold", type=float, default=10.0)
    parser.add_argument("--spo2-drop-threshold", type=float, default=2.0)
    args = parser.parse_args()

    raw_df = load_sleep_csv(args.csv_path)
    processed_df, metadata = preprocess_signals(raw_df)
    candidates = detect_rule_candidates(
        processed_df,
        min_event_seconds=args.min_event_seconds,
        airflow_drop_threshold_percent=args.airflow_drop_threshold,
        spo2_drop_threshold=args.spo2_drop_threshold,
    )
    print(
        json.dumps(
            {
                "preprocessing": metadata,
                "candidate_count": len(candidates),
                "candidates": [candidate.to_dict() for candidate in candidates],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
