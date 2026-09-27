const scanner = document.getElementById("scanner");
const fileInput = document.getElementById("fileInput");
const previewImg = document.getElementById("previewImg");
const results = document.getElementById("results");
const resultsBars = document.getElementById("resultsBars");
const topLabel = document.getElementById("topLabel");
const topConf = document.getElementById("topConf");
const errorMsg = document.getElementById("errorMsg");
const resetBtn = document.getElementById("resetBtn");
const feedbackForm = document.getElementById("feedbackForm");
const feedbackFields = document.getElementById("feedbackFields");
const feedbackComment = document.getElementById("feedbackComment");
const feedbackStatus = document.getElementById("feedbackStatus");
const feedbackSubmit = document.getElementById("feedbackSubmit");
let currentLabel = null;
let scanVersion = 0;

function resetFeedback() {
  currentLabel = null;
  feedbackForm.reset();
  feedbackFields.disabled = false;
  feedbackStatus.textContent = "";
  feedbackStatus.dataset.error = "false";
  feedbackSubmit.textContent = "Send feedback";
}

feedbackForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rating = feedbackForm.querySelector('input[name="rating"]:checked');
  if (!rating || !currentLabel || feedbackFields.disabled) return;
  const version = scanVersion;
  const payload = { predicted_label: currentLabel, looked_wrong: rating.value === "down", comment: feedbackComment.value.trim() };
  feedbackFields.disabled = true;
  feedbackSubmit.textContent = "Sending…";
  feedbackStatus.textContent = "";
  feedbackStatus.dataset.error = "false";
  try {
    const response = await fetch("/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error("Feedback was not saved.");
    if (version !== scanVersion) return;
    feedbackSubmit.textContent = "Feedback sent";
    feedbackStatus.textContent = "Thanks! Your feedback has been saved.";
  } catch (error) {
    if (version !== scanVersion) return;
    feedbackFields.disabled = false;
    feedbackSubmit.textContent = "Try sending again";
    feedbackStatus.dataset.error = "true";
    feedbackStatus.textContent = "Couldn't save your feedback. Your choices are still here—please try again.";
  }
});

function humanizeLabel(raw) {
  // Turns something like "Tomato___Early_blight" into "Early Blight"
  return raw
    .replace(/^Tomato_+/i, "")
    .replace(/_+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
  results.hidden = true;
}

function resetUI() {
  scanVersion += 1;
  resetFeedback();
  scanner.classList.remove("has-image", "scanning");
  previewImg.src = "";
  results.hidden = true;
  errorMsg.hidden = true;
  fileInput.value = "";
}

function renderResults(data) {
  resetFeedback();
  currentLabel = data.top.label;
  scanner.classList.remove("scanning");

  topLabel.textContent = humanizeLabel(data.top.label);
  topConf.textContent = `${data.top.confidence}% confidence`;

  resultsBars.innerHTML = "";
  data.predictions.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "bar-row" + (i === 0 ? " top" : "");
    row.innerHTML = `
      <span>${humanizeLabel(p.label)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${p.confidence}%"></span></span>
      <span>${p.confidence}%</span>
    `;
    resultsBars.appendChild(row);
  });

  results.hidden = false;
}

async function submitImage(file) {
  const version = ++scanVersion;
  resetFeedback();
  results.hidden = true;
  errorMsg.hidden = true;

  const reader = new FileReader();
  reader.onload = (e) => {
    if (version !== scanVersion) return;
    previewImg.src = e.target.result;
    scanner.classList.add("has-image");
  };
  scanner.classList.add("scanning");
  reader.readAsDataURL(file);

  const formData = new FormData();
  formData.append("image", file);

  try {
    const res = await fetch("/predict", { method: "POST", body: formData });
    const data = await res.json();
    if (version !== scanVersion) return;

    if (!res.ok) {
      scanner.classList.remove("scanning");
      showError(data.error || "Something went wrong reading that image.");
      return;
    }

    renderResults(data);
  } catch (err) {
    if (version !== scanVersion) return;
    scanner.classList.remove("scanning");
    showError("Couldn't reach the model. Try again in a moment.");
  }
}

scanner.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) submitImage(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((evt) =>
  scanner.addEventListener(evt, (e) => {
    e.preventDefault();
    scanner.classList.add("dragover");
  })
);

["dragleave", "drop"].forEach((evt) =>
  scanner.addEventListener(evt, (e) => {
    e.preventDefault();
    scanner.classList.remove("dragover");
  })
);

scanner.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) submitImage(file);
});

resetBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  resetUI();
});
