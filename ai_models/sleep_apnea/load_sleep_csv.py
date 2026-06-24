#!/usr/bin/env python3

import argparse
import json

from hybrid_pipeline_common import load_sleep_csv


def main():
    parser = argparse.ArgumentParser(description="Load a raw SleepSense CSV into a clean dataframe preview.")
    parser.add_argument("csv_path")
    args = parser.parse_args()

    df = load_sleep_csv(args.csv_path)
    summary = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "time_range_sec": [float(df["time_sec"].min()), float(df["time_sec"].max())],
        "preview": df.head(5).to_dict(orient="records"),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
