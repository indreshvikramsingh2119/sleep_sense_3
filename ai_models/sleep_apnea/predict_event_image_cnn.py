#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from hybrid_pipeline_common import DEFAULT_OUTPUT_DIR, run_hybrid_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Legacy hybrid apnea pipeline: raw CSV -> rule candidates -> event images -> CNN -> final report."
    )
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--pre-event-seconds", type=float, default=30.0)
    parser.add_argument("--post-event-seconds", type=float, default=30.0)
    parser.add_argument("--confidence-threshold", type=float, default=0.70)
    args = parser.parse_args()

    summary = run_hybrid_pipeline(
        csv_path=Path(args.csv_path),
        output_dir=Path(args.output_dir),
        pre_event_seconds=args.pre_event_seconds,
        post_event_seconds=args.post_event_seconds,
        confidence_threshold=args.confidence_threshold,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
