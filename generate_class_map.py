"""
Run this ONCE, locally, pointed at your training data directory, to lock
in the class index order Keras assigned during training (alphabetical
sort of subfolder names -- same logic as infer_class_names() in your
research repo's eval_utils.py).

This produces model/class_indices.json, which the app loads at startup.
Do this before deploying -- get it wrong and every prediction is silently
mislabeled with a confident-looking wrong class.

Usage:
    python generate_class_map.py /path/to/train_dir

Sanity check after running: open the printed JSON and confirm the order
matches what you saw when you originally trained (check any training
logs / notebook output where Keras printed "Found N images belonging to
3 classes" -- the order there should match this file exactly).
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_class_map.py /path/to/train_dir")
        sys.exit(1)

    train_dir = Path(sys.argv[1])
    if not train_dir.is_dir():
        print(f"Not a directory: {train_dir}")
        sys.exit(1)

    class_names = sorted(p.name for p in train_dir.iterdir() if p.is_dir())
    if not class_names:
        print(f"No subfolders found in {train_dir} -- is this the right path?")
        sys.exit(1)

    idx_to_class = {i: name for i, name in enumerate(class_names)}

    out_path = Path(__file__).resolve().parent / "model" / "class_indices.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(idx_to_class, f, indent=2)

    print(f"Wrote {out_path}\n")
    print(json.dumps(idx_to_class, indent=2))
    print("\nDouble check this order against your training logs before deploying.")


if __name__ == "__main__":
    main()



