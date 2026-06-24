import os
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from keras.preprocessing import image
import joblib

# Dataset Path
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "datasets", "train")
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "knn_model.pkl")
SCALER_SAVE_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")

print("Loading images for KNN training...")

# Load all images and flatten them
X = []
y = []
class_names = sorted([d for d in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH, d))])

for class_idx, class_name in enumerate(class_names):
    class_path = os.path.join(DATASET_PATH, class_name)
    for img_name in os.listdir(class_path):
        img_path = os.path.join(class_path, img_name)
        try:
            img = image.load_img(img_path, target_size=(128, 128))
            img_array = image.img_to_array(img)
            img_flat = img_array.flatten()
            X.append(img_flat)
            y.append(class_idx)
            print(f"Loaded: {class_name}/{img_name}")
        except Exception as e:
            print(f"Error loading {img_path}: {e}")

X = np.array(X)
y = np.array(y)

print(f"\nDataset shape: {X.shape}")
print(f"Classes: {class_names}")

# Normalize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train KNN (k=5)
print("\nTraining KNN classifier (k=5)...")
knn_model = KNeighborsClassifier(n_neighbors=5)
knn_model.fit(X_scaled, y)

# Save model and scaler
joblib.dump(knn_model, MODEL_SAVE_PATH)
joblib.dump(scaler, SCALER_SAVE_PATH)
joblib.dump(class_names, os.path.join(os.path.dirname(__file__), "class_names.pkl"))

print(f"KNN Model saved to {MODEL_SAVE_PATH}")
print(f"Scaler saved to {SCALER_SAVE_PATH}")
print("Training Complete!")
