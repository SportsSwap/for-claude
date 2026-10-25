// Sawnx: small conveniences only. Every action also works as a plain form without this file.
"use strict";

// Ask before deleting: any submit button with data-confirm. Without this file the button just works.
document.addEventListener("submit", function (e) {
  const button = e.submitter;
  const message = button && button.dataset ? button.dataset.confirm : "";
  if (message && !window.confirm(message)) e.preventDefault();
});

// Import: drag files onto the drop zone; one "Read for the return / Store only" choice per file.
(function () {
  const input = document.getElementById("files");
  const choices = document.getElementById("choices");
  const zone = document.querySelector("[data-dropzone]");
  if (!input || !choices) return;
  const folders = JSON.parse(choices.dataset.folders || "[]");

  function option(value, text, selected) {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    if (selected) o.selected = true;
    return o;
  }

  function render() {
    choices.replaceChildren();
    Array.from(input.files).forEach(function (file, i) {
      const row = document.createElement("div");
      row.className = "file-choice";
      const name = document.createElement("span");
      name.className = "mono small";
      name.textContent = "File " + (i + 1) + ": " + file.name;
      const mode = document.createElement("select");
      mode.name = "mode_" + i;
      mode.setAttribute("aria-label", "What to do with file " + (i + 1));
      const storeOnly = choices.dataset.storeOnly === "yes";
      mode.append(option("read", "Read for the return", !storeOnly), option("store", "Store only", storeOnly));
      mode.hidden = storeOnly;
      const folder = document.createElement("select");
      folder.name = "folder_" + i;
      folder.setAttribute("aria-label", "Folder for file " + (i + 1));
      folders.forEach(function (f) { folder.append(option(f, "Store in " + f, f === "Other")); });
      folder.hidden = !storeOnly;
      mode.addEventListener("change", function () { folder.hidden = mode.value !== "store"; });
      row.append(name, mode, folder);
      choices.append(row);
    });
  }

  input.addEventListener("change", render);
  if (zone) {
    ["dragenter", "dragover"].forEach(function (t) {
      zone.addEventListener(t, function (e) { e.preventDefault(); zone.classList.add("over"); });
    });
    ["dragleave", "drop"].forEach(function (t) {
      zone.addEventListener(t, function (e) { e.preventDefault(); zone.classList.remove("over"); });
    });
    zone.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        render();
      }
    });
  }
})();

// Import progress: send the files one at a time, so the bar can say how many are done and roughly how
// long the rest will take. Without this script the form sends them all at once, as before.
function timeLeft(doneSeconds, remaining) {
  if (remaining <= 0) return "";
  if (!doneSeconds.length) return "working out time left…";
  const average = doneSeconds.reduce(function (a, b) { return a + b; }, 0) / doneSeconds.length;
  const seconds = average * remaining;
  if (seconds < 60) return "about " + Math.max(5, Math.ceil(seconds / 5) * 5) + " s left";
  return "about " + Math.round(seconds / 60) + " min left";
}

function took(seconds) {
  seconds = Math.round(seconds);
  return seconds < 60 ? seconds + " s" : Math.floor(seconds / 60) + " min " + (seconds % 60) + " s";
}

(function () {
  const input = document.getElementById("files");
  const panel = document.getElementById("progress");
  if (!input || !panel || !window.fetch || !window.FormData) return;
  const form = input.form;
  const bar = document.getElementById("progress-bar");
  const text = document.getElementById("progress-text");
  const time = document.getElementById("progress-time");
  const results = document.getElementById("progress-results");

  function addResults(html) {
    const t = document.createElement("template");
    t.innerHTML = html;
    t.content.querySelectorAll(".result").forEach(function (row) { results.append(row); });
  }

  function failed(position) {
    const row = document.createElement("div");
    row.className = "result";
    const strong = document.createElement("strong");
    strong.textContent = "File " + position;
    const problem = document.createElement("span");
    problem.className = "high";
    problem.textContent = "Sawnx couldn't import this file. Try it again on its own.";
    row.append(strong, ": ", problem);
    results.append(row);
  }

  form.addEventListener("submit", async function (e) {
    const files = Array.from(input.files);
    if (!files.length) return;
    e.preventDefault();
    const button = e.submitter || form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    panel.hidden = false;
    results.replaceChildren();
    document.getElementById("progress-done").hidden = true;
    bar.max = files.length;
    bar.value = 0;
    panel.scrollIntoView({ block: "start" });
    const seconds = [];
    const started = Date.now();
    for (let i = 0; i < files.length; i++) {
      text.textContent = "Reading " + (i + 1) + " of " + files.length;
      time.textContent = " · " + timeLeft(seconds, files.length - i);
      const data = new FormData();
      form.querySelectorAll('input[type="hidden"], input[type="radio"]:checked').forEach(function (el) {
        data.append(el.name, el.value);
      });
      const mode = form.elements["mode_" + i];
      const folder = form.elements["folder_" + i];
      if (mode) data.append("mode_0", mode.value);
      if (folder) data.append("folder_0", folder.value);
      data.append("files", files[i]);
      data.append("fragment", "1");
      data.append("first_position", String(i + 1));
      const t0 = Date.now();
      try {
        const resp = await fetch(form.action, { method: "POST", body: data, credentials: "same-origin" });
        if (!resp.ok) throw new Error(String(resp.status));
        addResults(await resp.text());
      } catch (err) {
        failed(i + 1);
      }
      seconds.push((Date.now() - t0) / 1000);
      bar.value = i + 1;
    }
    text.textContent = "Done: " + files.length + " file" + (files.length === 1 ? "" : "s") + " in " +
      took((Date.now() - started) / 1000);
    time.textContent = "";
    document.getElementById("progress-done").hidden = false;
    form.reset();
    document.getElementById("choices").replaceChildren();
    if (button) button.disabled = false;
  });
})();

// Recent searches: the last clients found by search, shown under the search box while it has focus.
(function () {
  const box = document.getElementById("topq");
  const menu = document.getElementById("recent-menu");
  if (!box || !menu) return;
  box.addEventListener("focus", function () { menu.hidden = false; });
  box.addEventListener("keydown", function (e) { if (e.key === "Escape") menu.hidden = true; });
  box.form.addEventListener("focusout", function (e) {
    if (!box.form.contains(e.relatedTarget)) menu.hidden = true;
  });
})();

// Figures: a tick or a new label saves its row straight away.
document.querySelectorAll("[data-autosave]").forEach(function (el) {
  el.addEventListener("change", function () {
    const form = el.form;
    if (form) form.requestSubmit();
  });
});

// Document list: the heading checkbox ticks or clears every row.
document.querySelectorAll("[data-tickall]").forEach(function (all) {
  all.addEventListener("change", function () {
    const table = all.closest("table");
    if (!table) return;
    table.querySelectorAll('tbody input[type="checkbox"][name="key"]').forEach(function (box) { box.checked = all.checked; });
  });
});
