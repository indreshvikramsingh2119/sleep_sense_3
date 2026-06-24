#!/usr/bin/env python3

import argparse
import json

from hybrid_pipeline_common import load_sleep_csv, preprocess_signals


def main():
    parser = argparse.ArgumentParser(description="Smooth and normalize raw SleepSense signals.")
    parser.add_argument("csv_path")
    parser.add_argument("--smoothing-seconds", type=float, default=1.5)
    args = parser.parse_args()

    raw_df = load_sleep_csv(args.csv_path)
    processed_df, metadata = preprocess_signals(raw_df, smoothing_seconds=args.smoothing_seconds)
    metadata["preview"] = processed_df.head(5).to_dict(orient="records")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
