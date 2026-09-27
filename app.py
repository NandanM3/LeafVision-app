from pathlib import Path
import os

import numpy as np
import cv2
from flask import Flask, request, jsonify, render_template

from inference.predict import load_class_map, load_leafvision_model, predict
import feedback_store

APP_ROOT = Path(__file__).resolve().parent
MODEL_PATH = APP_ROOT / "model" / "leafvision_efficientnet_v1.keras"
CLASS_MAP_PATH = APP_ROOT / "model" / "class_indices.json"

app = Flask(__name__)
feedback_store.initialize_storage()

# Loaded once at startup, not per-request -- model loading is slow and
# request handlers should stay fast.
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
    try:
        scan_count = feedback_store.increment_scan_count()
    except OSError:
        app.logger.warning("Scan counter unavailable; returning prediction without a count.")
        scan_count = None
    return jsonify({"predictions": results, "top": results[0], "scan_count": scan_count})


@app.route("/stats")
def stats_route():
    try:
        return jsonify({"scan_count": feedback_store.get_scan_count()})
    except OSError:
        return jsonify({"error": "Scan count temporarily unavailable."}), 503


@app.route("/feedback", methods=["POST"])
def feedback_route():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400
    predicted_label = data.get("predicted_label", "")
    looked_wrong = data.get("looked_wrong")
    comment = data.get("comment", "")

    if not isinstance(predicted_label, str) or predicted_label not in idx_to_class.values():
        return jsonify({"error": "Invalid predicted_label."}), 400
    if not isinstance(looked_wrong, bool):
        return jsonify({"error": "Choose thumbs up or thumbs down."}), 400
    if not isinstance(comment, str) or len(comment) > 500:
        return jsonify({"error": "Comment must be text of at most 500 characters."}), 400

    try:
        feedback_store.save_feedback(predicted_label, looked_wrong, comment)
    except OSError:
        app.logger.warning("Could not save feedback.")
        return jsonify({"error": "Could not save feedback. Please try again."}), 503
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Render assigns a port dynamically via $PORT. Hugging Face Spaces and
    # local dev both expect 7860, so that stays the fallback.
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=False, host="0.0.0.0", port=port)
