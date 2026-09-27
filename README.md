# LeafVision
 
**A CNN-based tomato leaf disease classifier — live demo, open for feedback.**
 
 **Try it:** [Will add link once deployed]
 **Research behind it:** [LeafVision-ML] [Link to Repo]
 
 
---
 
## What this is
 
LeafVision is an image classifier that identifies early blight, late blight,
and healthy tomato leaves from a single photo. It's built on EfficientNet-B0
with transfer learning, and it's the applied counterpart to an ongoing
research study on how reliable CNN-based plant disease detection actually is
outside of clean, curated datasets.
 
This repo is the **public demo**. It exists to put the model in front of
real people, on real (often imperfect) photos, and collect honest feedback
on where it holds up and where it breaks.
 
## Why I'm asking for feedback
 
Most plant disease classifiers report strong numbers on clean lab datasets(this one included). 
The more useful question is what happens on a photo taken in the field under imperfect conditions. 
That gap between lab accuracy and field accuracy is well documented in the literature and is the specific thing my
research is measuring.
 
This demo is a live, informal extension of that question. If you try it, the
most useful thing you can do is:
 
- Upload a clean, well-lit leaf photo, and separately
- Upload a rough, real-world one (blurry, backlit, at a distance)
and tell me if the prediction changes, and whether either one was just
plain wrong. Mislabeled predictions are genuinely useful data, not an
inconvenience please report them.
 
**To give feedback:** upload a photo, choose thumbs up or thumbs down beneath
the prediction, optionally add a comment, and press **Send feedback**.
No account is required.

Feedback records contain the predicted label, whether it looked wrong, an
optional comment (up to 500 characters), and a UTC timestamp. These are tester
opinions, not verified accuracy measurements or unique tester counts.

On Render, set `DATABASE_URL` to your Neon PostgreSQL connection string. The app
creates its tables at startup and stores feedback and scan counts outside Render,
so deployments and restarts do not erase them. A missing connection string stops
startup on Render instead of silently collecting feedback on temporary storage.

For local development without `DATABASE_URL`, feedback and counts still save to
`data/store.json` (excluded from Git). This local mode supports one process only.
Existing JSON records are not automatically imported when switching to PostgreSQL;
keep a backup if you have already collected real feedback.

See [database setup and code walkthrough](docs/database.md) for Render settings,
an explanation of every database change, and validation steps.
 
## The research behind it
 
The demo model is one output of a broader study evaluating CNN reliability
under simulated real-world degradation:  brightness/contrast shifts,
Gaussian blur, Gaussian noise, and resolution reduction, each at multiple
severities. 

Some early findings from that work:
 
- Clean-condition baseline: **94.98% accuracy**, 94.55% macro F1 across held-out test images
- The model is more robust to noise than expected, but **blur causes the sharpest accuracy collapse** of any tested condition
- Under degradation, the model tends to **miss disease rather than raise false alarms**. Recall drops faster than precision, which matters more than the headline accuracy number for real deployment decisions
Full methodology, results, and writeup: see the [LeafVision-ML]( will link my repo later) repo.
 
## Status
 
This is an early-stage public demo, not a finished product and not
agronomic advice. Three disease classes are supported
today (early blight, late blight, healthy). Expanding coverage and
improving field robustness are both active work.
 
