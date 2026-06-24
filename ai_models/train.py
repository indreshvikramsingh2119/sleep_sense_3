import json
import os
import re
from collections import Counter

import numpy as np
from keras import layers
from keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
from keras.models import Sequential
from keras.preprocessing import image

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:  
    pass


BASE_DIR = os.path.dirname(__file__)
DATASET_PATH = os.path.join(BASE_DIR, "datasets")
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_SAVE_PATH = os.path.join(MODELS_DIR, "image_classifier_model.keras")
CLASS_NAMES_PATH = os.path.join(MODELS_DIR, "class_names.json")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
IGNORED_LABEL_FOLDERS = {"datasets", "train", "test"}


def infer_label(image_path):
    parent_folder = os.path.basename(os.path.dirname(image_path)).lower()
    if parent_folder not in IGNORED_LABEL_FOLDERS:
        return parent_folder

    file_name = os.path.basename(image_path).lower()
    match = re.match(r"[a-z_-]+", file_name)
    if not match:
        return None

    return match.group(0).strip("_-")


def collect_labeled_images(dataset_path):
    labeled_images = []

    for root, _, file_names in os.walk(dataset_path):
        for file_name in sorted(file_names):
            if not file_name.lower().endswith(IMAGE_EXTENSIONS):
                continue

            image_path = os.path.join(root, file_name)
            label = infer_label(image_path)
            if label:
                labeled_images.append((image_path, label))

    return labeled_images


def load_images(labeled_images, class_names):
    label_to_index = {label: index for index, label in enumerate(class_names)}
    x_values = []
    y_values = []

    for image_path, label in labeled_images:
        img = image.load_img(image_path, target_size=(224, 224))
        img_array = image.img_to_array(img)
        x_values.append(img_array)
        y_values.append(label_to_index[label])

    x_values = preprocess_input(np.array(x_values, dtype=np.float32))
    y_values = np.array(y_values, dtype=np.int32)
    return x_values, y_values


labeled_images = collect_labeled_images(DATASET_PATH)
if not labeled_images:
    raise FileNotFoundError(f"No labeled images found in: {DATASET_PATH}")

class_counts = Counter(label for _, label in labeled_images)
class_names = sorted(class_counts)

if len(class_names) < 2:
    raise ValueError("At least two image classes are required for training.")

print("Dataset image counts:")
for class_name in class_names:
    print(f"- {class_name}: {class_counts[class_name]} images")

print("Classes:", class_names)

x_train, y_train = load_images(labeled_images, class_names)

base_model = MobileNetV2(
    include_top=False,
    weights="imagenet",
    input_shape=(224, 224, 3),
    pooling="avg",
)
base_model.trainable = False

model = Sequential(
    [
        layers.Input(shape=(224, 224, 3)),
        base_model,
        layers.Dropout(0.2),
        layers.Dense(len(class_names), activation="softmax"),
    ]
)

model.compile(
    optimizer="adam",
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

model.fit(
    x_train,
    y_train,
    epochs=25,
    batch_size=min(8, len(x_train)),
    verbose=1,
)

os.makedirs(MODELS_DIR, exist_ok=True)
model.save(MODEL_SAVE_PATH)

with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as file:
    json.dump(class_names, file, indent=2)

print(f"Model saved to: {MODEL_SAVE_PATH}")
print(f"Class names saved to: {CLASS_NAMES_PATH}")
print("Training Complete")
        