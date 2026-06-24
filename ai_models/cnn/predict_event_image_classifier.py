#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.metrics import confusion_matrix


CURRENT_DIR = Path(__file__).resolve().parent
SLEEP_APNEA_DIR = CURRENT_DIR.parent / "sleep_apnea"
MODELS_DIR = SLEEP_APNEA_DIR / "models"
META_PATH = MODELS_DIR / "event_image_model_meta.json"
CLASS_NAMES_PATH = MODELS_DIR / "event_image_class_names.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def default_input_path():
    valid_dir = SLEEP_APNEA_DIR / "event_image_dataset" / "valid"
    if valid_dir.exists():
        return str(valid_dir)
    return str(SLEEP_APNEA_DIR / "event_image_dataset" / "val")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Predict sleep apnea event image classes from a file or folder."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=default_input_path(),
        help="Image file or folder. Defaults to event_image_dataset/valid, falling back to val.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="How many top class probabilities to print for each image.",
    )
    return parser.parse_args()


def collect_image_paths(input_path: Path):
    if input_path.is_file():
        return [input_path]
    return sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def infer_actual_label(image_path: Path, class_names):
    parent_name = image_path.parent.name
    if parent_name in class_names:
        return parent_name
    return None


def load_model_bundle():
    with open(META_PATH, "r", encoding="utf-8") as file:
        metadata = json.load(file)
    with open(CLASS_NAMES_PATH, "r", encoding="utf-8") as file:
        class_names = json.load(file)
    model_path = Path(metadata["model_path"])
    backend = metadata.get("backend", "unknown")
    if backend == "sklearn_knn":
        model = joblib.load(model_path)
    else:
        raise ValueError(f"Unsupported backend for reconstructed predictor: {backend}")
    return model, class_names, metadata


def prepare_image(image_path: Path, metadata):
    size = tuple(metadata.get("image_size", [32, 32]))
    color_mode = metadata.get("color_mode", "grayscale")
    image = Image.open(image_path)
    image = image.convert("L" if color_mode == "grayscale" else "RGB")
    image = image.resize(size)
    array = np.asarray(image, dtype=np.float32)
    if color_mode == "grayscale":
        return array.reshape(-1) / 255.0
    return array.reshape(-1) / 255.0


def predict_one(model, class_names, image_path: Path, metadata):
    vector = prepare_image(image_path, metadata)
    probs = model.predict_proba([vector])[0]
    pred_index = int(np.argmax(probs))
    confidence = float(probs[pred_index])
    ranked = [
        {"label": class_names[index], "confidence": float(prob)}
        for index, prob in sorted(enumerate(probs), key=lambda item: item[1], reverse=True)
    ]
    return class_names[pred_index], confidence, ranked


def main():
    args = parse_args()
    input_path = Path(args.input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    model, class_names, metadata = load_model_bundle()
    image_paths = collect_image_paths(input_path)
    if not image_paths:
        raise FileNotFoundError(f"No image files found in: {input_path}")

    if len(image_paths) == 1:
        label, confidence, ranked = predict_one(model, class_names, image_paths[0], metadata)
        print(f"Model backend: {metadata.get('backend', 'unknown')}")
        print(f"Input image: {image_paths[0]}")
        print(f"Prediction: {label}")
        print(f"Confidence: {confidence:.4f}")
        print("Top probabilities:")
        for row in ranked[: max(1, args.top_k)]:
            print(f"  {row['label']}: {row['confidence']:.4f}")
        return

    print(f"Model backend: {metadata.get('backend', 'unknown')}")
    print(f"Input folder: {input_path}")
    print(f"Total images found: {len(image_paths)}\n")

    counts = {}
    actual_counts = {}
    correct_predictions = 0
    evaluated_predictions = 0
    actual_labels = []
    predicted_labels = []

    for image_path in image_paths:
        label, confidence, ranked = predict_one(model, class_names, image_path, metadata)
        actual_label = infer_actual_label(image_path, class_names)
        counts[label] = counts.get(label, 0) + 1

        if actual_label:
            actual_counts[actual_label] = actual_counts.get(actual_label, 0) + 1
            evaluated_predictions += 1
            actual_labels.append(actual_label)
            predicted_labels.append(label)
            is_correct = actual_label == label
            if is_correct:
                correct_predictions += 1
            status = "OK" if is_correct else "WRONG"
            if confidence < 0.4:
                status += ", LOW_CONF"
            print(f"{image_path}: actual={actual_label}, predicted={label} ({confidence:.4f}) [{status}]")
        else:
            print(f"{image_path}: predicted={label} ({confidence:.4f})")

        top_rows = ", ".join(
            f"{row['label']}={row['confidence']:.4f}" for row in ranked[: max(1, args.top_k)]
        )
        print(f"  top: {top_rows}")

    print("\nPrediction counts:")
    for label in class_names:
        if label in counts:
            print(f"{label}: {counts[label]}")

    if actual_counts:
        print("\nActual counts:")
        for label in class_names:
            if label in actual_counts:
                print(f"{label}: {actual_counts[label]}")

    if evaluated_predictions:
        accuracy = correct_predictions / evaluated_predictions
        print(f"\nMatched labels: {correct_predictions}/{evaluated_predictions}")
        print(f"Folder-based accuracy: {accuracy:.4f}")

        label_to_index = {label: index for index, label in enumerate(class_names)}
        y_true = [label_to_index[label] for label in actual_labels]
        y_pred = [label_to_index[label] for label in predicted_labels]
        matrix = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))

        print("\nConfusion matrix (rows=actual, cols=predicted):")
        print("        " + " ".join(f"{label:>6}" for label in class_names))
        for row_label, row in zip(class_names, matrix):
            print(f"{row_label:>6} " + " ".join(f"{value:>6}" for value in row))

        print("\nPer-class accuracy:")
        for label, row in zip(class_names, matrix):
            total = int(np.sum(row))
            correct = int(row[label_to_index[label]])
            per_class_accuracy = correct / total if total else 0.0
            print(f"{label}: {correct}/{total} = {per_class_accuracy:.4f}")


if __name__ == "__main__":
    main()
