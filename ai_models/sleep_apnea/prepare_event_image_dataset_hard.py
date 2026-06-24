#!/usr/bin/env python3

import argparse
import itertools
import json
import shutil
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from event_image_pipeline import (
    OUTPUT_DIR,
    MODELS_DIR,
    CLASS_NAMES_PATH,
    CHANNEL_ORDER,
    load_window_labels,
    load_raw_signals,
    load_metadata,
    resample_window,
)


HARD_OUTPUT_DIR = OUTPUT_DIR.parent / "event_image_dataset_hard"
NEARBY_ROW_GAP = 600

TARGET_CLASSES_DEFAULT = ["CSA", "HSA", "MSA", "OSA"]

Y_LIMITS = {
    "airflow": (-10, 110),
    "spo2": (50, 105),
    "pulse": (30, 180),
    "body_movement": (-10, 110),
    "snoring": (-10, 110),
}

CHANNEL_COLOR = "#111111"

# Important:
# Pre/post ko chhota rakha hai, warna raw signal boundary ke bahar window jaati hai.
TRAIN_TEMPLATES = [
    {"name": "tpl_train_a", "pre": 6, "post": 6, "noise": 0.5, "scale": 0.98},
    {"name": "tpl_train_b", "pre": 8, "post": 8, "noise": 0.9, "scale": 1.00},
    {"name": "tpl_train_c", "pre": 10, "post": 10, "noise": 1.2, "scale": 1.02},
]

VALID_TEMPLATES = [
    {"name": "tpl_valid_a", "pre": 7, "post": 9, "noise": 1.0, "scale": 0.99},
    {"name": "tpl_valid_b", "pre": 9, "post": 7, "noise": 1.3, "scale": 1.01},
]

TEST_TEMPLATES = [
    {"name": "tpl_test_unseen_a", "pre": 6, "post": 8, "noise": 1.1, "scale": 0.98},
    {"name": "tpl_test_unseen_b", "pre": 8, "post": 6, "noise": 1.3, "scale": 1.02},
]

TRAIN_REPEAT = 40
VALID_REPEAT = 3
TEST_REPEAT = 3

FALLBACK_TEMPLATE = {
    "name": "tpl_fallback",
    "pre": 3,
    "post": 3,
    "noise": 0.8,
    "scale": 1.0,
}


def normalize_label(label):
    return str(label).strip().upper()


def choose_template(rng, split_name):
    if split_name == "train":
        templates = TRAIN_TEMPLATES
    elif split_name == "valid":
        templates = VALID_TEMPLATES
    else:
        templates = TEST_TEMPLATES

    return templates[int(rng.integers(0, len(templates)))]


def make_row_key(row, sample_rate_hz):
    return int(round(float(row["start_sec"]) * float(sample_rate_hz)))


def safe_window_bounds(signal_df, start_sec, end_sec, template, min_seconds=3.0):
    signal_min = float(signal_df["time_sec"].min())
    signal_max = float(signal_df["time_sec"].max())

    render_start = float(start_sec) - float(template["pre"])
    render_end = float(end_sec) + float(template["post"])

    # Clamp inside signal range.
    render_start = max(signal_min, render_start)
    render_end = min(signal_max, render_end)

    if render_end <= render_start:
        return None

    if (render_end - render_start) < min_seconds:
        return None

    return render_start, render_end


def can_render(signal_df, start_sec, end_sec, sample_rate_hz):
    bounds = safe_window_bounds(
        signal_df=signal_df,
        start_sec=start_sec,
        end_sec=end_sec,
        template=FALLBACK_TEMPLATE,
        min_seconds=3.0,
    )

    if bounds is None:
        return False

    try:
        resample_window(
            signal_df,
            bounds[0],
            bounds[1],
            sample_rate_hz=sample_rate_hz,
        )
        return True
    except ValueError:
        return False


def filter_window_df(window_df, signal_df, target_classes, sample_rate_hz):
    df = window_df.copy()

    df["label"] = df["label"].map(normalize_label)
    df = df[df["label"].isin(target_classes)].copy()

    df["start_sec"] = df["start_sec"].astype(float)
    df["end_sec"] = df["end_sec"].astype(float)
    df = df[df["end_sec"] > df["start_sec"]].copy()

    df["row_key"] = df.apply(lambda row: make_row_key(row, sample_rate_hz), axis=1)

    # Same row + same label duplicate remove.
    df = df.drop_duplicates(subset=["row_key", "label"], keep="first").copy()

    # Same row par multiple classes artificial hoti hain. Un rows ko remove karo.
    row_label_counts = df.groupby("row_key")["label"].nunique()
    bad_rows = set(row_label_counts[row_label_counts > 1].index)
    if bad_rows:
        df = df[~df["row_key"].isin(bad_rows)].copy()

    # Pehle sirf renderable windows rakho.
    renderable_mask = []
    for _, row in df.iterrows():
        ok = can_render(
            signal_df=signal_df,
            start_sec=float(row["start_sec"]),
            end_sec=float(row["end_sec"]),
            sample_rate_hz=sample_rate_hz,
        )
        renderable_mask.append(ok)

    df = df[renderable_mask].copy()

    return df.reset_index(drop=True), len(bad_rows)


def split_by_label(df, target_classes, valid_ratio, test_ratio, seed):
    rng = np.random.default_rng(seed)

    split_indices = {
        "train": [],
        "valid": [],
        "test": [],
    }

    row_to_indices = {}
    row_to_label = {}
    for index, row in df.iterrows():
        row_key = int(row["row_key"])
        row_to_indices.setdefault(row_key, []).append(index)
        row_to_label[row_key] = str(row["label"])

    sorted_rows = sorted(row_to_indices)
    row_clusters = []
    current_cluster = []
    previous_row = None

    for row_key in sorted_rows:
        if previous_row is None or (row_key - previous_row) <= NEARBY_ROW_GAP:
            current_cluster.append(row_key)
        else:
            row_clusters.append(current_cluster)
            current_cluster = [row_key]
        previous_row = row_key

    if current_cluster:
        row_clusters.append(current_cluster)

    total_counts = Counter(df["label"].tolist())
    target_valid = {
        label: max(1, int(round(total_counts[label] * valid_ratio)))
        for label in target_classes
        if total_counts[label] > 0
    }
    target_test = {
        label: max(1, int(round(total_counts[label] * test_ratio)))
        for label in target_classes
        if total_counts[label] > 0
    }

    cluster_infos = []
    for cluster_rows in row_clusters:
        cluster_infos.append(
            {
                "rows": cluster_rows,
                "counts": Counter(row_to_label[row_key] for row_key in cluster_rows),
            }
        )

    split_names = ("train", "valid", "test")
    best_assignment = None
    best_score = None

    cluster_order = list(range(len(cluster_infos)))
    rng.shuffle(cluster_order)
    ordered_clusters = [cluster_infos[index] for index in cluster_order]

    for assignment in itertools.product(split_names, repeat=len(ordered_clusters)):
        per_split_counts = {split_name: Counter() for split_name in split_names}
        for split_name, cluster_info in zip(assignment, ordered_clusters):
            per_split_counts[split_name].update(cluster_info["counts"])

        if any(
            per_split_counts[split_name].get(label, 0) <= 0
            for label in target_classes
            for split_name in split_names
        ):
            continue

        score = 0
        for label in target_classes:
            score += abs(per_split_counts["valid"].get(label, 0) - target_valid.get(label, 0))
            score += abs(per_split_counts["test"].get(label, 0) - target_test.get(label, 0))

        if best_score is None or score < best_score:
            best_score = score
            best_assignment = assignment

    if best_assignment is None:
        raise ValueError(
            "Could not create a gap-safe train/valid/test split with all classes present."
        )

    for split_name, cluster_info in zip(best_assignment, ordered_clusters):
        for row_key in cluster_info["rows"]:
            split_indices[split_name].extend(row_to_indices[row_key])

    label_split_counts = {
        split_name: Counter(df.loc[indices, "label"].tolist())
        for split_name, indices in split_indices.items()
    }

    for label in target_classes:
        if any(label_split_counts[split_name].get(label, 0) <= 0 for split_name in ("train", "valid", "test")):
            raise ValueError(
                f"Class {label} does not have enough separated windows after gap-safe split. "
                "Need at least 1 train, 1 valid, and 1 test sample."
            )

    return split_indices


def jitter_sampled(sampled, rng, template):
    output = {}

    for channel in CHANNEL_ORDER:
        y = sampled[channel].astype(np.float64).copy()
        noise = float(template["noise"])

        if channel == "spo2":
            channel_noise = noise * 0.20
        elif channel == "pulse":
            channel_noise = noise * 0.60
        else:
            channel_noise = noise

        y = y * float(template["scale"])
        y = y + rng.normal(0, channel_noise, size=len(y))

        if channel == "spo2":
            y = np.clip(y, 50, 105)
        elif channel == "pulse":
            y = np.clip(y, 30, 180)
        else:
            y = np.clip(y, -20, 120)

        output[channel] = y

    return output


def render_hard_image(relative_time, sampled, output_path):
    fig, axes = plt.subplots(
        len(CHANNEL_ORDER),
        1,
        figsize=(6, 6),
        dpi=140,
        sharex=True,
    )

    fig.patch.set_facecolor("white")

    for axis, channel in zip(axes, CHANNEL_ORDER):
        axis.plot(
            relative_time,
            sampled[channel],
            color=CHANNEL_COLOR,
            linewidth=1.2,
        )

        axis.set_ylabel(channel, fontsize=8)
        axis.set_ylim(*Y_LIMITS[channel])
        axis.grid(False)
        axis.tick_params(axis="both", labelsize=8)

    axes[-1].set_xlabel("seconds", fontsize=9)

    # No title, no class name, no event type text.
    fig.tight_layout(rect=(0, 0, 1, 1))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, facecolor="white")
    plt.close(fig)


def render_one(row, split_name, output_dir, target_sample_rate_hz, signal_df, rng, variant_id=0):
    label = str(row["label"])
    row_key = int(row["row_key"])
    start_sec = float(row["start_sec"])
    end_sec = float(row["end_sec"])

    if "window_index" in row:
        window_index = int(row["window_index"])
    else:
        window_index = int(row.name)

    template = choose_template(rng, split_name)

    # Pehle selected template try karo, agar fail ho to fallback template use karo.
    templates_to_try = [template, FALLBACK_TEMPLATE]

    for chosen_template in templates_to_try:
        bounds = safe_window_bounds(
            signal_df=signal_df,
            start_sec=start_sec,
            end_sec=end_sec,
            template=chosen_template,
            min_seconds=3.0,
        )

        if bounds is None:
            continue

        try:
            relative_time, sampled = resample_window(
                signal_df,
                bounds[0],
                bounds[1],
                sample_rate_hz=target_sample_rate_hz,
            )
        except ValueError:
            continue

        sampled = jitter_sampled(sampled, rng, chosen_template)

        duration = max(1, int(round(end_sec - start_sec)))
        pre = int(chosen_template["pre"])
        post = int(chosen_template["post"])

        file_name = (
            f"{label.lower()}_row{row_key}_"
            f"s{pre}_d{duration}_{chosen_template['name']}_post{post}_"
            f"win{window_index:04d}_v{variant_id:03d}.png"
        )

        output_path = output_dir / split_name / label / file_name
        render_hard_image(relative_time, sampled, output_path)

        used_fallback = chosen_template["name"] == FALLBACK_TEMPLATE["name"]
        return True, used_fallback

    return False, False


def ensure_class_dirs(output_dir, target_classes):
    for split_name in ["train", "valid", "test"]:
        for label in target_classes:
            (output_dir / split_name / label).mkdir(parents=True, exist_ok=True)


def count_output_images(output_dir, target_classes):
    summary = {}

    for split_name in ["train", "valid", "test"]:
        summary[split_name] = {}
        for label in target_classes:
            class_dir = output_dir / split_name / label
            summary[split_name][label] = len(list(class_dir.glob("*.png")))

    return summary


def validate_summary(summary, target_classes):
    problems = []

    for split_name in ["train", "valid", "test"]:
        for label in target_classes:
            if summary[split_name][label] <= 0:
                problems.append(f"{split_name}/{label} has 0 images")

    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(HARD_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--valid-ratio", type=float, default=0.10)
    parser.add_argument("--test-ratio", type=float, default=0.10)
    parser.add_argument("--classes", default="CSA,HSA,MSA,OSA")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    target_classes = [
        normalize_label(x)
        for x in args.classes.split(",")
        if x.strip()
    ]

    rng = np.random.default_rng(args.seed)
    output_dir = Path(args.output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)

    window_df = load_window_labels()
    signal_df = load_raw_signals()
    metadata = load_metadata()

    target_sample_rate_hz = float(metadata.get("target_sample_rate_hz", 10.0))

    df, removed_multi_class_rows = filter_window_df(
        window_df=window_df,
        signal_df=signal_df,
        target_classes=target_classes,
        sample_rate_hz=target_sample_rate_hz,
    )

    if df.empty:
        raise ValueError(
            "No renderable target windows found after filtering. "
            "Check processed/window_labels.csv and raw signal time range."
        )

    available_counts = Counter(df["label"].tolist())

    print("Renderable target windows after filtering:")
    for label in target_classes:
        print(f"  {label}: {available_counts.get(label, 0)}")
    print(f"Removed multi-class rows: {removed_multi_class_rows}")
    print()

    missing = [
        label
        for label in target_classes
        if available_counts.get(label, 0) < 3
    ]

    if missing:
        raise ValueError(
            f"Not enough renderable windows for classes: {missing}. "
            "Need at least 3 renderable windows per class."
        )

    split_indices = split_by_label(
        df=df,
        target_classes=target_classes,
        valid_ratio=args.valid_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    ensure_class_dirs(output_dir, target_classes)

    skipped = Counter()
    fallback_count = Counter()

    for split_name, indices in split_indices.items():
        if split_name == "train":
            repeat_count = TRAIN_REPEAT
        elif split_name == "valid":
            repeat_count = VALID_REPEAT
        else:
            repeat_count = TEST_REPEAT

        for index in indices:
            row = df.loc[index]
            label = str(row["label"])

            for variant_id in range(repeat_count):
                ok, used_fallback = render_one(
                    row=row,
                    split_name=split_name,
                    output_dir=output_dir,
                    target_sample_rate_hz=target_sample_rate_hz,
                    signal_df=signal_df,
                    rng=rng,
                    variant_id=variant_id,
                )

                if not ok:
                    skipped[f"{split_name}/{label}"] += 1

                if used_fallback:
                    fallback_count[f"{split_name}/{label}"] += 1

    summary = count_output_images(output_dir, target_classes)
    problems = validat. e_summary(summary, target_classes)

    if problems:
        print("Hard dataset generation failed/incomplete.")
        print("Problems:")
        for problem in problems:
            print(f"  - {problem}")

        print()
        print("Skipped windows:")
        for key, count in skipped.items():
            print(f"  {key}: {count}")

        raise ValueError("Hard dataset incomplete.")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as file:
        json.dump(target_classes, file, indent=2)

    print("Hard event image dataset created successfully")
    print(f"Output: {output_dir}")
    print(f"Classes: {target_classes}")
    print()

    for split_name in ["train", "valid", "test"]:
        print(split_name.upper())
        for label in target_classes:
            print(f"  {label}: {summary[split_name][label]}")
        print()

    if skipped:
        print("Skipped windows:")
        for key, count in skipped.items():
            print(f"  {key}: {count}")
    else:
        print("Skipped windows: 0")

    if fallback_count:
        print()
        print("Fallback template used:")
        for key, count in fallback_count.items():
            print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
