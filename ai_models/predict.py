import argparse
import json
import os
from collections import Counter

import numpy as np
from keras.applications.mobilenet_v2 import preprocess_input
from keras.models import load_model
from keras.preprocessing import image


BASE_DIR = os.path.dirname(__file__)
DEFAULT_IMAGE_PATH = os.path.join(BASE_DIR, "test.jpg")
MODEL_PATH = os.path.join(BASE_DIR, "models", "image_classifier_model.keras")
CLASS_NAMES_PATH = os.path.join(BASE_DIR, "models", "class_names.json")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")


def collect_images(path):
    if os.path.isfile(path):
        return [path] if path.lower().endswith(IMAGE_EXTENSIONS) else []

    image_paths = []
    for root, _, file_names in os.walk(path):
        for file_name in sorted(file_names):
            if file_name.lower().endswith(IMAGE_EXTENSIONS):
                image_paths.append(os.path.join(root, file_name))

    return sorted(image_paths)


def infer_actual_label(image_path, input_path, class_names):
    if os.path.isfile(input_path):
        return None

    relative_path = os.path.relpath(image_path, input_path)
    label_folder = relative_path.split(os.sep, 1)[0].lower()
    class_lookup = {class_name.lower(): class_name for class_name in class_names}
    return class_lookup.get(label_folder)


def load_custom_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not os.path.exists(CLASS_NAMES_PATH):
        raise FileNotFoundError(f"Class names not found: {CLASS_NAMES_PATH}")

    with open(CLASS_NAMES_PATH, "r", encoding="utf-8") as file:
        class_names = json.load(file)

    return load_model(MODEL_PATH), class_names


def load_image_array(image_path):
    img = image.load_img(image_path, target_size=(224, 224), color_mode="rgb")
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    return preprocess_input(img_array)


def predict_image(model, class_names, image_path):
    prediction = model.predict(load_image_array(image_path), verbose=0)[0]
    predicted_index = int(np.argmax(prediction))
    label = class_names[predicted_index]
    confidence = float(prediction[predicted_index])
    return label, confidence


def parse_args():
    parser = argparse.ArgumentParser(
        description="Predict one image or count predictions for a folder using the custom trained model."
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default=DEFAULT_IMAGE_PATH,
        help="Image or folder path. Example: python3 ai_models/predict.py ai_models/datasets",
    )
    return parser.parse_args()


args = parse_args()

if not os.path.exists(args.image_path):
    raise FileNotFoundError(f"Image not found: {args.image_path}")

image_paths = collect_images(args.image_path)
if not image_paths:
    raise FileNotFoundError(f"No image files found in: {args.image_path}")

try:
    model, class_names = load_custom_model()
except Exception as error:
    print("Could not load custom model.")
    print("First run: python3 ai_models/train.py")
    print(f"Error: {error}")
    raise SystemExit(1)

if len(image_paths) == 1:
    label, confidence = predict_image(model, class_names, image_paths[0])

    print("Model used: custom trained model")
    print("Input image:", image_paths[0])
    print("Prediction:", label)
    print(f"Confidence: {confidence:.4f}")
else:
    counts = Counter()
    actual_counts = Counter()
    correct_counts = Counter()
    correct_total = 0
    labeled_total = 0

    print("Model used: custom trained model")
    print("Input folder:", args.image_path)
    print(f"Total images found: {len(image_paths)}\n")

    for image_path in image_paths:
        label, confidence = predict_image(model, class_names, image_path)
        actual_label = infer_actual_label(image_path, args.image_path, class_names)
        counts[label] += 1

        if actual_label:
            actual_counts[actual_label] += 1
            labeled_total += 1

            if label == actual_label:
                correct_total += 1
                correct_counts[actual_label] += 1
                result = "correct"
            else:
                result = "wrong"

            print(
                f"{image_path}: predicted={label} actual={actual_label} "
                f"({confidence:.4f}) {result}"
            )
        else:
            print(f"{image_path}: {label} ({confidence:.4f})")

    print("\nPrediction counts:")
    for label, count in counts.most_common():
        print(f"- {label}: {count}")

    if labeled_total:
        accuracy = correct_total / labeled_total
        print(f"\nAccuracy: {accuracy:.2%} ({correct_total}/{labeled_total})")

        print("\nPer-class accuracy:")
        for label in class_names:
            total = actual_counts[label]
            if total == 0:
                continue

            correct = correct_counts[label]
            print(f"- {label}: {correct / total:.2%} ({correct}/{total})")
    else:
        print(
            "\nAccuracy unavailable: put test images inside class folders "
            "like ai_models/test_images/cat/image1.jpg"
        )
