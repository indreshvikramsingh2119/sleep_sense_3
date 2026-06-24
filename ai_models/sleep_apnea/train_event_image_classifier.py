#!/usr/bin/env python3

import argparse
import re
import shutil
import tempfile
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from event_image_model import DEFAULT_COLOR_MODE, DEFAULT_IMAGE_SIZE, MODEL_PATH, save_model_bundle
from event_image_pipeline import CLASS_NAMES_PATH, OUTPUT_DIR, prepare_event_image_dataset


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
NEARBY_ROW_GAP = 600
CLEAN_OUTPUT_DIR = OUTPUT_DIR.parent / "event_image_dataset_clean"


def _get_validation_split_dir(dataset_dir: Path):
    for split_name in ("val", "valid"):
        split_dir = dataset_dir / split_name 
        if split_dir.exists():
            return split_dir
    return dataset_dir / "val"


def _event_key(path: Path):
    match = re.search(r"row(\d+)", path.name.lower())
    if match:
        return match.group(1)
    return path.stem.lower()


def _event_row(path: Path):
    match = re.search(r"row(\d+)", path.name.lower())
    if match:
        return int(match.group(1))
    return None


def _collect_event_rows(split_dir: Path, class_names: list[str]):
    rows = []
    for class_name in class_names:
        class_dir = split_dir / class_name
        if not class_dir.exists():
            continue
        for image_path in class_dir.glob("*"):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            row = _event_row(image_path)
            if row is not None:
                rows.append(row)
    return rows


def _find_nearby_leaks(train_rows: list[int], val_rows: list[int], gap: int):
    nearby_leaks = []
    for val_row in val_rows:
        for train_row in train_rows:
            if abs(val_row - train_row) <= gap:
                nearby_leaks.append((train_row, val_row))
                break
    return nearby_leaks


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train a stable image classifier on sleep apnea event images."
    )
    parser.add_argument("--epochs", type=int, default=1, help="Kept for CLI compatibility; ignored by KNN.")
    parser.add_argument("--batch-size", type=int, default=16, help="Kept for CLI compatibility; ignored by KNN.")
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
        help="Skip the old CSV-to-image preparation step and use the current image dataset as-is.",
    )
    parser.add_argument(
        "--classes",
        default="CSA,HSA,OSA,MSA",
        help="Comma-separated class names to include in training. Default: CSA,HSA,OSA,MSA",
    )
    return parser.parse_args()


def _class_image_map(dataset_dir: Path):
    class_map = {}
    split_dirs = [dataset_dir / "train", _get_validation_split_dir(dataset_dir)]
    for split_dir in split_dirs:
        if not split_dir.exists() or not split_dir.is_dir():
            continue
        for class_dir in split_dir.iterdir():
            if not class_dir.is_dir():
                continue
            image_paths = sorted(
                path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            )
            class_map.setdefault(class_dir.name, []).extend(image_paths)
    return {label: paths for label, paths in sorted(class_map.items()) if paths}


def _parse_selected_classes(classes_arg: str):
    selected = [item.strip() for item in classes_arg.split(",") if item.strip()]
    if len(selected) < 2:
        raise ValueError("At least two classes are required for training.")
    return selected


def _filter_existing_split(dataset_dir: Path, selected_classes):
    temp_root = Path(tempfile.mkdtemp(prefix="event_image_filtered_"))
    summary = {"train": {}, "valid": {}}
    split_sources = {
        "train": dataset_dir / "train",
        "valid": _get_validation_split_dir(dataset_dir),
    }

    for split_name, split_dir in split_sources.items():
        if not split_dir.exists() or not split_dir.is_dir():
            continue
        for label in selected_classes:
            class_dir = split_dir / label
            if not class_dir.exists():
                continue
            image_paths = sorted(
                path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            )
            if not image_paths:
                continue
            target_dir = temp_root / split_name / label
            target_dir.mkdir(parents=True, exist_ok=True)
            for index, source_path in enumerate(image_paths, start=1):
                target_path = target_dir / f"{index:04d}_{source_path.stem}{source_path.suffix.lower()}"
                shutil.copy2(source_path, target_path)
            summary[split_name][label] = len(image_paths)

    return temp_root, summary


def _split_is_usable(dataset_dir: Path):
    train_dir = dataset_dir / "train"
    valid_dir = _get_validation_split_dir(dataset_dir)
    if not train_dir.exists() or not valid_dir.exists():
        return False

    train_classes = {
        class_dir.name: len([p for p in class_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])
        for class_dir in train_dir.iterdir()
        if class_dir.is_dir()
    }
    valid_classes = {
        class_dir.name: len([p for p in class_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])
        for class_dir in valid_dir.iterdir()
        if class_dir.is_dir()
    }
    class_names = sorted(set(train_classes) | set(valid_classes))
    if len(class_names) < 2:
        return False
    has_all_classes = all(train_classes.get(label, 0) > 0 and valid_classes.get(label, 0) > 0 for label in class_names)
    if not has_all_classes:
        return False

    train_rows = _collect_event_rows(train_dir, class_names)
    val_rows = _collect_event_rows(valid_dir, class_names)
    nearby_leaks = _find_nearby_leaks(train_rows, val_rows, NEARBY_ROW_GAP)
    return not nearby_leaks


def _rebuild_dataset_split(dataset_dir: Path, val_ratio: float, seed: int):
    class_map = _class_image_map(dataset_dir)
    if len(class_map) < 2:
        raise ValueError("At least two class folders with images are required for training.")

    temp_root = CLEAN_OUTPUT_DIR
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)
    split_summary = {"train": {}, "valid": {}}

    label_totals = {label: len(image_paths) for label, image_paths in class_map.items()}
    for label, count in label_totals.items():
        if count < 2:
            raise ValueError(f"Class '{label}' needs at least 2 images for train/val split.")


    grouped_paths: dict[tuple[str, int | str], list[Path]] = {}
    unlabeled_counter = 0
    for label, image_paths in class_map.items():
        for image_path in image_paths:
            row = _event_row(image_path)
            if row is None:
                unlabeled_counter += 1
                group_key = ("fallback", f"{label}:{unlabeled_counter}")
            else:
                group_key = ("row", row)
            grouped_paths.setdefault(group_key, []).append(image_path)

    numeric_rows = sorted(key[1] for key in grouped_paths if key[0] == "row")
    grouped_keys = []
    current_cluster = []
    previous_row = None
    for row in numeric_rows:
        if previous_row is None or row - previous_row <= NEARBY_ROW_GAP:
            current_cluster.append(("row", row))
        else:
            grouped_keys.append(current_cluster)
            current_cluster = [("row", row)]
        previous_row = row
    if current_cluster:
        grouped_keys.append(current_cluster)

    for key in grouped_paths:
        if key[0] == "fallback":
            grouped_keys.append([key])

    rng = np.random.default_rng(seed)
    cluster_order = list(range(len(grouped_keys)))
    rng.shuffle(cluster_order)

    target_val_counts = {
        label: min(label_totals[label] - 1, max(1, int(round(label_totals[label] * val_ratio))))
        for label in class_map
    }
    val_counts = {label: 0 for label in class_map}
    val_group_indices = set()

    def cluster_label_counts(cluster_keys):
        counts = {label: 0 for label in class_map}
        for cluster_key in cluster_keys:
            for image_path in grouped_paths[cluster_key]:
                counts[image_path.parent.name] += 1
        return counts

    for cluster_index in cluster_order:
        cluster_counts = cluster_label_counts(grouped_keys[cluster_index])
        should_add = False
        for label, count in cluster_counts.items():
            if count == 0:
                continue
            if val_counts[label] >= target_val_counts[label]:
                continue
            remaining_train = label_totals[label] - (val_counts[label] + count)
            if remaining_train < 1:
                should_add = False
                break
            should_add = True
        if not should_add:
            continue
        for label, count in cluster_counts.items():
            val_counts[label] += count
        val_group_indices.add(cluster_index)

    train_assignments = {label: [] for label in class_map}
    val_assignments = {label: [] for label in class_map}
    for cluster_index, cluster_keys in enumerate(grouped_keys):
        target_map = val_assignments if cluster_index in val_group_indices else train_assignments
        for cluster_key in cluster_keys:
            for image_path in grouped_paths[cluster_key]:
                target_map[image_path.parent.name].append(image_path)

    for label in class_map:
        train_paths = sorted(train_assignments[label])
        val_paths = sorted(val_assignments[label])
        if not train_paths or not val_paths:
            raise ValueError(
                f"Could not build a leakage-safe split for class '{label}'. "
                f"Train={len(train_paths)}, val={len(val_paths)}"
            )

        split_summary["train"][label] = len(train_paths)
        split_summary["valid"][label] = len(val_paths)

        for split_name, split_paths in (("train", train_paths), ("valid", val_paths)):
            class_dir = temp_root / split_name / label
            class_dir.mkdir(parents=True, exist_ok=True)
            for index, source_path in enumerate(split_paths, start=1):
                target_path = class_dir / f"{index:04d}_{source_path.stem}{source_path.suffix.lower()}"
                shutil.copy2(source_path, target_path)

    return temp_root, split_summary


def _load_split_arrays(split_dir: Path, class_names: list[str]):
    features = []
    labels = []
    for label_index, class_name in enumerate(class_names):
        class_dir = split_dir / class_name
        for image_path in sorted(class_dir.glob("*")):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            image_obj = Image.open(image_path).convert("L").resize(DEFAULT_IMAGE_SIZE)
            array = np.asarray(image_obj, dtype=np.float32).reshape(-1) / 255.0
            features.append(array)
            labels.append(label_index)
    return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int32)


def main():
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    selected_classes = _parse_selected_classes(args.classes)

    if not args.skip_prepare:
        summary = prepare_event_image_dataset(seed=args.seed)
        print("Prepared event image dataset:")
        print(f"  Source CSV: {summary['source_csv']}")
        print(f"  Output directory: {summary['output_dir']}")
        dataset_dir = OUTPUT_DIR

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    temp_dataset_dir = None
    split_summary = None
    if _split_is_usable(dataset_dir):
        prepared_dataset_dir = dataset_dir
    else:
        temp_dataset_dir, split_summary = _rebuild_dataset_split(
            dataset_dir=dataset_dir,
            val_ratio=args.val_ratio,
            seed=args.seed,
        )
        prepared_dataset_dir = temp_dataset_dir

    filtered_dataset_dir, filtered_summary = _filter_existing_split(
        dataset_dir=prepared_dataset_dir,
        selected_classes=selected_classes,
    )
    if split_summary is None:
        split_summary = filtered_summary
    else:
        split_summary["filtered"] = filtered_summary

    train_dir = filtered_dataset_dir / "train"
    val_dir = filtered_dataset_dir / "valid"
    class_names = sorted(filtered_summary["train"].keys())

    train_keys = set()
    val_keys = set()
    for class_name in class_names:
        for image_path in (train_dir / class_name).glob("*"):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                train_keys.add(_event_key(image_path))
        for image_path in (val_dir / class_name).glob("*"):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                val_keys.add(_event_key(image_path))

    leaked_keys = train_keys & val_keys
    print(f"Leakage check: train unique events={len(train_keys)}, val unique events={len(val_keys)}")
    if leaked_keys:
        raise ValueError(
            f"DATA LEAKAGE FOUND: {len(leaked_keys)} same events are present in both train and val. "
            f"Examples: {sorted(leaked_keys)[:10]}"
        )

    train_rows = _collect_event_rows(train_dir, class_names)
    val_rows = _collect_event_rows(val_dir, class_names)
    nearby_leaks = _find_nearby_leaks(train_rows, val_rows, NEARBY_ROW_GAP)

    print(
        f"Nearby leakage check: {len(nearby_leaks)} val events are within {NEARBY_ROW_GAP} rows of train events"
    )
    if nearby_leaks:
        raise ValueError(
            f"NEARBY DATA LEAKAGE FOUND: {len(nearby_leaks)} validation events are too close to training events. "
            f"Examples train/val rows: {nearby_leaks[:10]}"
        )

    X_train, y_train = _load_split_arrays(train_dir, class_names)
    X_val, y_val = _load_split_arrays(val_dir, class_names)

    if len(X_train) == 0 or len(X_val) == 0:
        raise ValueError("Training and validation splits must both contain images.")

    model = make_pipeline(
        StandardScaler(),
        KNeighborsClassifier(n_neighbors=3, weights="distance"),
    )

    print("Training event image classifier...")
    print(f"Dataset directory: {dataset_dir}")
    print(f"Selected classes: {selected_classes}")
    print(f"Classes: {class_names}")
    print(f"Image size: {DEFAULT_IMAGE_SIZE}")
    print(f"Color mode: {DEFAULT_COLOR_MODE}")
    if split_summary:
        print(f"Rebuilt split counts: {split_summary}")

    model.fit(X_train, y_train)
    val_prediction = model.predict(X_val)
    val_probability = model.predict_proba(X_val)
    accuracy = accuracy_score(y_val, val_prediction)
    loss = log_loss(y_val, val_probability, labels=list(range(len(class_names))))

    save_model_bundle(model, class_names, image_size=DEFAULT_IMAGE_SIZE, color_mode=DEFAULT_COLOR_MODE)

    print(f"Validation loss: {loss:.4f}")
    print(f"Validation accuracy: {accuracy:.4f}")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Class names saved to: {CLASS_NAMES_PATH}")
    print("Event image training complete.")

    shutil.rmtree(filtered_dataset_dir, ignore_errors=True)
    if temp_dataset_dir is not None and temp_dataset_dir != CLEAN_OUTPUT_DIR:
        shutil.rmtree(temp_dataset_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
