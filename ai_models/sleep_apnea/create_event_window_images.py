#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from hybrid_pipeline_common import (
    create_event_window_image,
    detect_rule_candidates,
    load_sleep_csv,
    preprocess_signals,
)


def main():
    parser = argparse.ArgumentParser(description="Legacy: render CNN input images for detected event candidates.")
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "hybrid_pipeline_output" / "event_images"))
    parser.add_argument("--pre-event-seconds", type=float, default=30.0)
    parser.add_argument("--post-event-seconds", type=float, default=30.0)
    args = parser.parse_args()

    raw_df = load_sleep_csv(args.csv_path)
    processed_df, _ = preprocess_signals(raw_df)
    candidates = detect_rule_candidates(processed_df)

    output_dir = Path(args.output_dir)
    created = []
    for candidate in candidates:
        image_path = output_dir / f"{candidate.event_id}.png"
        create_event_window_image(
            signal_df=processed_df,
            candidate=candidate,
            output_path=image_path,
            pre_event_seconds=args.pre_event_seconds,
            post_event_seconds=args.post_event_seconds,
        )
        created.append({"event_id": candidate.event_id, "image_path": str(image_path)})

    print(json.dumps({"image_count": len(created), "images": created}, indent=2))


if __name__ == "__main__":
    main()
