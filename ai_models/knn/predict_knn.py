import os
import numpy as np
from keras.preprocessing import image
import joblib

# Paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "knn_model.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")
CLASS_NAMES_PATH = os.path.join(os.path.dirname(__file__), "class_names.pkl")
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "test.jpg")

# Load model, scaler, and class names
knn_model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
class_names = joblib.load(CLASS_NAMES_PATH)

# Load test image
img = image.load_img(TEST_IMAGE_PATH, target_size=(128, 128))
img_array = image.img_to_array(img)
img_flat = img_array.flatten()

# Normalize
img_scaled = scaler.transform([img_flat])

# Predict
prediction = knn_model.predict(img_scaled)
confidence = knn_model.predict_proba(img_scaled)

result = class_names[prediction[0]]
confidence_score = np.max(confidence)

print(f"KNN Prediction: {result}")
print(f"Confidence: {confidence_score:.4f}")
