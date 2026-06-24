#!/usr/bin/env python3

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix


CURRENT_DIR = Path(__file__).resolve().parent
SLEEP_APNEA_DIR = CURRENT_DIR.parent / "sleep_apnea"
MODELS_DIR = SLEEP_APNEA_DIR / "models"

MODEL_PATH = MODELS_DIR / "event_image_cnn_custom.keras"
IMAGE_SUFFIXES = {".bmp", ".jpg", ".jpeg", ".png", ".webp"}


def load_model_bundle():
    model = tf.keras.models.load_model(MODEL_PATH)
    class_names = list(getattr(model, "output_names", []) or [])
    meta_path = MODELS_DIR / "event_image_cnn_meta.json"
    if meta_path.exists():
        import json

        with open(meta_path, "r", encoding="utf-8") as file:
            meta = json.load(file)
    else:
        meta = {}
    class_names_path = Path(meta.get("class_names_path", MODELS_DIR / "event_image_cnn_class_names.json"))
    if class_names_path.exists():
        import json

        with open(class_names_path, "r", encoding="utf-8") as file:
            class_names = json.load(file)
    return model, class_names, meta


def collect_image_paths(input_path: Path):
    if input_path.is_file():
        return [input_path]

    paths = []
    for class_dir in sorted(input_path.iterdir()):
        if not class_dir.is_dir():
            continue
        for path in sorted(class_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                paths.append(path)
    return paths


def load_image_for_model(image_path: Path, image_size, channels: int):
    image = Image.open(image_path).convert("L" if channels == 1 else "RGB")
    image = image.resize(image_size)
    array = np.asarray(image, dtype=np.float32)
    if channels == 1:
        array = array[..., None]
    return array


def actual_label_from_path(image_path: Path, class_names):
    parent = image_path.parent.name
    if parent in class_names:
        return parent
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", help="Image file or folder path")
    args = parser.parse_args()

    input_path = Path(args.input_path)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    model, class_names, _ = load_model_bundle()
    _, height, width, channels = model.input_shape
    image_paths = collect_image_paths(input_path)

    if not image_paths:
        raise ValueError(f"No images found in: {input_path}")

    print("Model backend: keras_custom_cnn")
    print(f"Model path: {MODEL_PATH}")
    print(f"Input folder: {input_path}")
    print(f"Total images found: {len(image_paths)}")
    print(f"Classes: {class_names}")
    print()

    y_true = []
    y_pred = []
    prediction_counts = {label: 0 for label in class_names}
    actual_counts = {label: 0 for label in class_names}

    for image_path in image_paths:
        array = load_image_for_model(image_path, (width, height), channels)
        probs = model.predict(np.expand_dims(array, axis=0), verbose=0)[0]
        pred_index = int(np.argmax(probs))
        label = class_names[pred_index]
        confidence = float(probs[pred_index])
        actual_label = actual_label_from_path(image_path, class_names)

        prediction_counts[label] += 1
        if actual_label:
            actual_counts[actual_label] += 1
            y_true.append(class_names.index(actual_label))
            y_pred.append(pred_index)
            status = "OK" if actual_label == label else "WRONG"
            print(f"{image_path}: actual={actual_label}, predicted={label} ({confidence:.4f}) [{status}]")
        else:
            print(f"{image_path}: predicted={label} ({confidence:.4f})")

    if y_true:
        cm = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))
        print(f"\nAccuracy: {accuracy_score(y_true, y_pred):.4f}")
        print("\nConfusion matrix (rows=actual, cols=predicted):")
        print("        " + " ".join(f"{label:>6}" for label in class_names))
        for i, row in enumerate(cm):
            print(f"{class_names[i]:>6} " + " ".join(f"{value:>6}" for value in row))


if __name__ == "__main__":
    main()
