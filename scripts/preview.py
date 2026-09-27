"""Local UI preview with sample predictions and no saved tester data."""
from pathlib import Path

from flask import Flask, jsonify, render_template

ROOT = Path(__file__).resolve().parents[1]
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
SAMPLE = {
    "top": {"label": "Tomato___Early_blight", "confidence": 87.4},
    "predictions": [
        {"label": "Tomato___Early_blight", "confidence": 87.4},
        {"label": "Tomato___Late_blight", "confidence": 9.2},
        {"label": "Tomato___healthy", "confidence": 3.4},
    ],
}


@app.get("/")
def index():
    html = render_template("index.html")
    banner = '<p style="margin:0;padding:12px 24px;background:#d9a441;color:#141f10;text-align:center">UI preview · Sample prediction · Feedback is not saved</p>'
    script = """<script>
    fetch('/sample').then(r => r.json()).then(renderResults);
    new MutationObserver(() => {
      if (feedbackStatus.textContent === 'Thanks! Your feedback has been saved.') {
        feedbackStatus.textContent = 'Thanks! Preview submission complete (not saved).';
      }
    }).observe(feedbackStatus, {childList: true});
    </script>"""
    return html.replace("<body>", "<body>" + banner).replace("</body>", script + "</body>")


@app.get("/sample")
@app.post("/predict")
def sample():
    return jsonify(SAMPLE)


@app.post("/feedback")
def feedback():
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7861, debug=False)
