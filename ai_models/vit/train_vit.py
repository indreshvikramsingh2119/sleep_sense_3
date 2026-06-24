import os
import ssl

# Bypass SSL certification verification (necessary on some macOS setups for urllib downloads)
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

import tensorflow as tf
from keras import layers
from keras.models import Model
from keras.applications import ResNet50V2
from keras.utils import image_dataset_from_directory
from keras.optimizers import Adam
from keras.callbacks import EarlyStopping, ModelCheckpoint

# Dataset Paths
DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sleep_apnea", "event_image_dataset", "train"))
VAL_DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sleep_apnea", "event_image_dataset", "val"))
MODEL_SAVE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "vit_model.h5"))

print("Loading dataset for ResNet50V2 Model...")

# Load Datasets
train_dataset = image_dataset_from_directory(
    DATASET_PATH,
    image_size=(224, 224),
    batch_size=16,
    shuffle=True,
    seed=42
)

val_dataset = image_dataset_from_directory(
    VAL_DATASET_PATH,
    image_size=(224, 224),
    batch_size=16,
    shuffle=False
)

# Class Names
class_names = train_dataset.class_names
print(f"Classes: {class_names}")

# Load ResNet50V2 pretrained on ImageNet
backbone = ResNet50V2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights='imagenet'
)

# Enable training on top layers of backbone, freeze lower layers
backbone.trainable = True
for layer in backbone.layers[:120]:
    layer.trainable = False

# Build model
inputs = layers.Input(shape=(224, 224, 3))
# ResNet50V2 expects inputs normalized in [-1, 1] range (preprocess_input or rescaling is fine)
x = layers.Rescaling(1./127.5, offset=-1.)(inputs)
x = backbone(x, training=False)
x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.35)(x)
x = layers.Dense(128, activation='relu')(x)
x = layers.Dropout(0.25)(x)
outputs = layers.Dense(len(class_names), activation='softmax')(x)

model = Model(inputs, outputs)

# Compile
model.compile(
    optimizer=Adam(learning_rate=1e-5),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Callbacks
callbacks = [
    EarlyStopping(
        monitor='val_accuracy',
        mode='max',
        patience=12,
        restore_best_weights=True,
        verbose=1
    ),
    ModelCheckpoint(
        filepath=MODEL_SAVE_PATH,
        monitor='val_accuracy',
        mode='max',
        save_best_only=True,
        verbose=1
    )
]

# Train
print("Training ResNet50V2 model (replacing simplified ViT)...")
model.fit(
    train_dataset,
    validation_data=val_dataset,
    epochs=40,
    callbacks=callbacks,
    verbose=1
)

print(f"Model saved to {MODEL_SAVE_PATH}")
print("Training Complete!")
