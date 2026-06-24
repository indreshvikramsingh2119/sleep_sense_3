from keras.models import load_model
from keras.preprocessing import image
import numpy as np
import os

# Paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "vit_model.h5")
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "test.jpg")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "sleep_apnea", "event_image_dataset", "train")

# Load Model
if not os.path.exists(MODEL_PATH):
    print(f"Model file {MODEL_PATH} not found. Train the model first.")
    exit(1)

model = load_model(MODEL_PATH)

# Load Image
if not os.path.exists(TEST_IMAGE_PATH):
    # Fallback to look for a test image in event_image_dataset
    print(f"Test image {TEST_IMAGE_PATH} not found. Attempting fallback...")
    for root, dirs, files in os.walk(DATASET_PATH):
        png_files = [f for f in files if f.endswith(".png")]
        if png_files:
            TEST_IMAGE_PATH = os.path.join(root, png_files[0])
            print(f"Using fallback test image: {TEST_IMAGE_PATH}")
            break

if not os.path.exists(TEST_IMAGE_PATH):
    print("No test image available to run predictions.")
    exit(1)

img = image.load_img(TEST_IMAGE_PATH, target_size=(224, 224))
img_array = image.img_to_array(img)

# Add Batch Dimension
img_array = np.expand_dims(img_array, axis=0)

# ResScaling is handled internally inside the ResNet50V2 model's layers.Rescaling

# Prediction
prediction = model.predict(img_array)

# Get class names
class_names = sorted([d for d in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH, d))])
result = class_names[np.argmax(prediction)]
confidence = np.max(prediction)

print(f"ResNet50V2 Model Prediction: {result}")
print(f"Confidence: {confidence:.4f}")
