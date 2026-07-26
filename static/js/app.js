const scanner = document.getElementById("scanner");
const fileInput = document.getElementById("fileInput");
const previewImg = document.getElementById("previewImg");
const results = document.getElementById("results");
const resultsBars = document.getElementById("resultsBars");
const topLabel = document.getElementById("topLabel");
const topConf = document.getElementById("topConf");
const errorMsg = document.getElementById("errorMsg");
const resetBtn = document.getElementById("resetBtn");

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
  scanner.classList.remove("has-image", "scanning");
  previewImg.src = "";
  results.hidden = true;
  errorMsg.hidden = true;
  fileInput.value = "";
}

function renderResults(data) {
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
  errorMsg.hidden = true;

  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    scanner.classList.add("has-image", "scanning");
  };
  reader.readAsDataURL(file);

  const formData = new FormData();
  formData.append("image", file);

  try {
    const res = await fetch("/predict", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      scanner.classList.remove("scanning");
      showError(data.error || "Something went wrong reading that image.");
      return;
    }

    renderResults(data);
  } catch (err) {
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
