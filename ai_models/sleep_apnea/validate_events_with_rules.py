#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from hybrid_pipeline_common import (
    create_event_window_image,
    detect_rule_candidates,
    load_cnn_model_bundle,
    load_sleep_csv,
    predict_event_image,
    preprocess_signals,
    validate_event_with_rules,
)


def main():
    parser = argparse.ArgumentParser(description="Run CNN prediction plus rule validation for detected candidates.")
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "hybrid_pipeline_output" / "event_images"))
    parser.add_argument("--confidence-threshold", type=float, default=0.70)
    args = parser.parse_args()

    raw_df = load_sleep_csv(args.csv_path)
    processed_df, _ = preprocess_signals(raw_df)
    candidates = detect_rule_candidates(processed_df)
    model, class_names, _ = load_cnn_model_bundle()
    output_dir = Path(args.output_dir)

    rows = []
    for candidate in candidates:
        image_path = output_dir / f"{candidate.event_id}.png"
        create_event_window_image(processed_df, candidate, image_path)
        cnn_prediction = predict_event_image(image_path, model, class_names)
        validation = validate_event_with_rules(candidate, cnn_prediction, confidence_threshold=args.confidence_threshold)
        rows.append(
            {
                **candidate.to_dict(),
                **validation,
                "image_path": str(image_path),
                "top_probabilities": cnn_prediction["top_probabilities"],
            }
        )

    print(json.dumps({"validated_count": len(rows), "events": rows}, indent=2))


if __name__ == "__main__":
    main()
