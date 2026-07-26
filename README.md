# LeafVision — App

Public demo for the LeafVision tomato leaf disease classifier. Upload a leaf
photo, get a prediction across three classes, see the full confidence
distribution.
live in the
separate `LeafVision-ML` research repo.
This repo is intentionally lean: it consumes the *output* of the research
work (a trained model + its preprocessing logic), not the training code
itself. Training, degradation experiments, and evaluation 

## 1. Get your model files in place

You need two files in `model/` before this will run:

```
model/
  leafvision_model.keras      <- copy from your LeafVision-ML repo
  class_indices.json          <- generate below, do NOT hand-write this
```

**Copy the trained model:**
```bash
cp /path/to/LeafVision-ML/models/your_model.keras model/leafvision_model.keras
```

**Generate the class map** — run this once, pointed at the training data
directory you originally trained on (the one with subfolders per class):

```bash
python generate_class_map.py /path/to/train_dir
```

This sorts the subfolder names alphabetically, exactly like Keras did
during training, and writes `model/class_indices.json`. Sanity-cheled.
eck the
printed order against your original training logs before moving on — a
silently wrong order means every prediction is confidently mislab
## 2. Run locally

```bash
python -3.11 -m venv .venv
.venv\Scripts\activate      
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:7860`. Drop in a few test leaf images (both clean
and rough/blurry phone photos) and confirm predictions look sane before
deploying.

## 3. Deploy to Hugging Face Spaces (recommended — free, fast, ML-native audience)

1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space)
   → SDK: **Docker** → visibility: Public.
2. In your local repo:
   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/leafvision
   ```
3. Your model file is likely >10MB — use Git LFS so it pushes cleanly:
   ```bash
   git lfs install
   git lfs track "*.keras"
   git add .gitattributes
   git add .
   git commit -m "Initial LeafVision app"
   git push space main
   ```
4. The Space builds the `Dockerfile` automatically and serves on port 7860.
   Build logs are visible in the Space's "Logs" tab if something fails.

Once it's live, the URL is share-ready: `https://huggingface.co/spaces/YOUR_USERNAME/leafvision`.

## 4. Getting feedback that's actually useful

Since the research angle is robustness under real-world degradation, when
you share this for feedback, explicitly ask people to try:
- A clean, well-lit photo
- A deliberately bad one — blurry, backlit, far away

The gap between those two responses *is* your research finding, made
tangible. Worth mentioning in whatever post/message you share the link in.

## Project structure

```
leafvision-app/
  app.py                   Flask entry point
  generate_class_map.py    one-time setup script (see step 1)
  inference/predict.py     preprocessing + inference, mirrors eval_utils.py
  templates/index.html     the demo page
  static/css/style.css
  static/js/app.js
  model/                   your .keras file + class_indices.json go here
  requirements.txt
  Dockerfile
```
