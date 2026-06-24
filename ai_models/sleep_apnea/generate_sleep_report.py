#!/usr/bin/env python3

import argparse
import json

from hybrid_pipeline_common import run_hybrid_pipeline


def main():
    parser = argparse.ArgumentParser(description="Generate the full hybrid sleep apnea event report from raw CSV.")
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--pre-event-seconds", type=float, default=30.0)
    parser.add_argument("--post-event-seconds", type=float, default=30.0)
    parser.add_argument("--confidence-threshold", type=float, default=0.70)
    args = parser.parse_args()

    summary = run_hybrid_pipeline(
        csv_path=args.csv_path,
        output_dir=args.output_dir or None,
        pre_event_seconds=args.pre_event_seconds,
        post_event_seconds=args.post_event_seconds,
        confidence_threshold=args.confidence_threshold,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
