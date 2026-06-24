#!/usr/bin/env python3

import argparse
import json
import shutil
from pathlib import Path
import sys

import numpy as np

try:
    import tensorflow as tf
    from keras import layers, models
    from keras.callbacks import EarlyStopping, ModelCheckpoint
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "TensorFlow/Keras is required for CNN training. Use a Python 3.11/3.12 "
        "environment with tensorflow installed before running train_event_image_cnn.py."
    ) from exc


CURRENT_DIR = Path(__file__).resolve().parent
SLEEP_APNEA_DIR = CURRENT_DIR.parent / "sleep_apnea"
if str(SLEEP_APNEA_DIR) not in sys.path:
    sys.path.insert(0, str(SLEEP_APNEA_DIR))

from event_image_pipeline import OUTPUT_DIR, prepare_event_image_dataset
from train_event_image_classifier import (
    CLEAN_OUTPUT_DIR,
    IMAGE_SUFFIXES,
    NEARBY_ROW_GAP,
    _collect_event_rows,
    _event_key,
    _filter_existing_split,
    _find_nearby_leaks,
    _get_validation_split_dir,
    _parse_selected_classes,
    _rebuild_dataset_split,
    _split_is_usable,
)


MODELS_DIR = SLEEP_APNEA_DIR / "models"
CNN_MODEL_PATH = MODELS_DIR / "event_image_cnn_custom.keras"
CNN_CLASS_NAMES_PATH = MODELS_DIR / "event_image_cnn_class_names.json"
CNN_META_PATH = MODELS_DIR / "event_image_cnn_meta.json"
DEFAULT_IMAGE_SIZE = (224, 224)


def parse_args():
    parser = argparse.ArgumentParser(description="Train a CNN on sleep apnea event images.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for dataset generation.")
    parser.add_argument(
        "--dataset-dir",
        default=str(OUTPUT_DIR),
        help="Dataset root containing train/ and valid/ folders. Legacy val/ is also supported.",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Validation split ratio used when rebuilding the split from existing images.",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip CSV-to-image preparation and use the current image dataset as-is.",
    )
    parser.add_argument(
        "--force-existing-split",
        action="store_true",
        help="Use existing train/val folders directly without rebuilding the split.",
    )
    parser.add_argument(
        "--skip-nearby-leakage-check",
        action="store_true",
        help="Allow train/val samples that are close in row index when comparing against a historical split.",
    )
    parser.add_argument(
        "--classes",
        default="CSA,HSA,OSA,MSA",
        help="Comma-separated class names to include in training. Default: CSA,HSA,OSA,MSA",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Initial training epochs.")
    parser.add_argument("--fine-tune-epochs", type=int, default=10, help="Fine-tuning epochs.")
    parser.add_argument("--batch-size", type=int, default=16, help="Mini-batch size.")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Initial learning rate.")
    parser.add_argument("--fine-tune-lr", type=float, default=1e-5, help="Fine-tuning learning rate.")
    parser.add_argument(
        "--random-init",
        action="store_true",
        help="Use random MobileNetV2 weights instead of ImageNet pretrained weights.",
    )
    return parser.parse_args()


def _build_datasets(train_dir: Path, val_dir: Path, class_names: list[str], image_size, batch_size: int, seed: int):
    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="int",
        class_names=class_names,
        image_size=image_size,
        batch_size=batch_size,
        shuffle=True,
        seed=seed,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_dir,
        labels="inferred",
        label_mode="int",
        class_names=class_names,
        image_size=image_size,
        batch_size=batch_size,
        shuffle=False,
    )
    autotune = tf.data.AUTOTUNE
    return train_ds.prefetch(autotune), val_ds.prefetch(autotune)


def _build_model(num_classes: int, random_init: bool):
    inputs = layers.Input(shape=(*DEFAULT_IMAGE_SIZE, 3))
    x = layers.Rescaling(1.0 / 255.0)(inputs)
    x = layers.Conv2D(32, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D()(x)
    x = layers.Conv2D(64, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D()(x)
    x = layers.Conv2D(128, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D()(x)
    x = layers.Conv2D(256, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D()(x)
    x = layers.Flatten()(x)
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.25)(x)
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    model = models.Model(inputs=inputs, outputs=outputs)
    return model, None


def _compute_class_weights(class_names: list[str], split_summary):
    counts = np.asarray([split_summary["train"].get(label, 0) for label in class_names], dtype=np.float32)
    if not counts.size or np.any(counts <= 0):
        return None
    total = float(np.sum(counts))
    return {index: total / (len(class_names) * float(count)) for index, count in enumerate(counts)}


def _count_split_images(split_dir: Path, selected_classes):
    counts = {}
    for label in selected_classes:
        class_dir = split_dir / label
        if not class_dir.exists():
            continue
        counts[label] = len(
            [path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        )
    return counts


def _save_metadata(class_names: list[str]):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CNN_CLASS_NAMES_PATH, "w", encoding="utf-8") as file:
        json.dump(class_names, file, indent=2)
    with open(CNN_META_PATH, "w", encoding="utf-8") as file:
        json.dump(
            {
                "model_path": str(CNN_MODEL_PATH),
                "class_names_path": str(CNN_CLASS_NAMES_PATH),
                "image_size": list(DEFAULT_IMAGE_SIZE),
                "backend": "keras_custom_cnn",
            },
            file,
            indent=2,
        )


def main():
    args = parse_args()
    tf.keras.utils.set_random_seed(args.seed)

    dataset_dir = Path(args.dataset_dir)
    selected_classes = _parse_selected_classes(args.classes)

    summary = None
    temp_dataset_dir = None
    split_summary = None

    if not args.skip_prepare:
        summary = prepare_event_image_dataset(seed=args.seed)
        print("Prepared event image dataset:")
        print(f"  Source CSV: {summary.get('source_csv')}")
        print(f"  Output directory: {summary.get('output_dir')}")
        dataset_dir = OUTPUT_DIR

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    if args.force_existing_split or _split_is_usable(dataset_dir):
        prepared_dataset_dir = dataset_dir
    else:
        temp_dataset_dir, split_summary = _rebuild_dataset_split(dataset_dir=dataset_dir, val_ratio=args.val_ratio, seed=args.seed)
        prepared_dataset_dir = temp_dataset_dir

    filtered_dataset_dir, filtered_summary = _filter_existing_split(prepared_dataset_dir, selected_classes)
    filtered_summary.setdefault("train", {})
    filtered_summary.setdefault("valid", {})

    train_dir = filtered_dataset_dir / "train"
    val_dir = filtered_dataset_dir / "valid"
    class_names = sorted(set(filtered_summary["train"].keys()) | set(filtered_summary["valid"].keys()))

    if len(class_names) < 2:
        raise ValueError("At least two classes with train/valid images are required for CNN training.")

    train_keys = set()
    val_keys = set()
    for class_name in class_names:
        for image_path in (train_dir / class_name).glob("*"):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                train_keys.add(_event_key(image_path))
        for image_path in (val_dir / class_name).glob("*"):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                val_keys.add(_event_key(image_path))

    leaked_keys = sorted(train_keys & val_keys)
    print(f"Leakage check: train unique events={len(train_keys)}, val unique events={len(val_keys)}")
    if leaked_keys:
        raise ValueError(f"DATA LEAKAGE FOUND: {len(leaked_keys)} same events are present in both train and val. Examples: {leaked_keys[:10]}")

    train_rows = _collect_event_rows(train_dir, class_names)
    val_rows = _collect_event_rows(val_dir, class_names)
    nearby_leaks = _find_nearby_leaks(train_rows, val_rows, NEARBY_ROW_GAP)
    print(f"Nearby leakage check: {len(nearby_leaks)} val events are within {NEARBY_ROW_GAP} rows of train events")
    if nearby_leaks and not args.skip_nearby_leakage_check:
        raise ValueError(
            f"NEARBY DATA LEAKAGE FOUND: {len(nearby_leaks)} validation events are too close to training events. "
            f"Examples train/val rows: {nearby_leaks[:10]}"
        )
    if nearby_leaks and args.skip_nearby_leakage_check:
        print("Skipping nearby leakage enforcement because --skip-nearby-leakage-check was provided.")

    train_ds, val_ds = _build_datasets(
        train_dir=train_dir,
        val_dir=val_dir,
        class_names=class_names,
        image_size=DEFAULT_IMAGE_SIZE,
        batch_size=args.batch_size,
        seed=args.seed,
    )

    model, base_model = _build_model(num_classes=len(class_names), random_init=args.random_init)
    class_weights = _compute_class_weights(class_names, filtered_summary)

    callbacks = [
        EarlyStopping(monitor="val_accuracy", patience=15, restore_best_weights=True, mode="max"),
        ModelCheckpoint(CNN_MODEL_PATH, monitor="val_accuracy", save_best_only=True, mode="max"),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_accuracy",
            factor=0.5,
            patience=5,
            min_lr=1e-6,
            mode="max",
        ),
    ]

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=args.learning_rate),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    print("Training event image CNN...")
    print(f"Dataset directory: {dataset_dir}")
    print(f"Selected classes: {selected_classes}")
    print(f"Classes: {class_names}")
    print(f"Image size: {DEFAULT_IMAGE_SIZE}")
    print(f"Batch size: {args.batch_size}")
    if split_summary:
        print(f"Rebuilt split counts: {split_summary}")

    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1,
    )

    if args.fine_tune_epochs > 0 and base_model is not None:
        base_model.trainable = True
        for layer in base_model.layers[:-30]:
            layer.trainable = False
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=args.fine_tune_lr),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.fine_tune_epochs,
            class_weight=class_weights,
            callbacks=callbacks,
            verbose=1,
        )

    model = tf.keras.models.load_model(CNN_MODEL_PATH)
    loss, accuracy = model.evaluate(val_ds, verbose=0)
    _save_metadata(class_names)

    print(f"Validation loss: {loss:.4f}")
    print(f"Validation accuracy: {accuracy:.4f}")
    print(f"Model saved to: {CNN_MODEL_PATH}")
    print(f"Class names saved to: {CNN_CLASS_NAMES_PATH}")
    print("Event image CNN training complete.")

    shutil.rmtree(filtered_dataset_dir, ignore_errors=True)
    if temp_dataset_dir is not None and temp_dataset_dir != CLEAN_OUTPUT_DIR:
        shutil.rmtree(temp_dataset_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
