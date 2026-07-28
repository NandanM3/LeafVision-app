from pathlib import Path
import os

import numpy as np
import cv2
from flask import Flask, request, jsonify, render_template

from inference.predict import load_class_map, load_leafvision_model, predict

APP_ROOT = Path(__file__).resolve().parent
MODEL_PATH = APP_ROOT / "model" / "leafvision_model.keras"
CLASS_MAP_PATH = APP_ROOT / "model" / "class_indices.json"

app = Flask(__name__)

# Loaded once at startup
print("Loading LeafVision model...")
model = load_leafvision_model(MODEL_PATH)
idx_to_class = load_class_map(CLASS_MAP_PATH)
print(f"Model loaded. Classes: {idx_to_class}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict_route():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded."}), 400

    file = request.files["image"]
    file_bytes = np.frombuffer(file.read(), np.uint8)
    img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return jsonify({"error": "Could not read that file. Try a JPG or PNG."}), 400

    results = predict(model, img_bgr, idx_to_class)
    return jsonify({"predictions": results, "top": results[0]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=False, host="0.0.0.0", port=port)