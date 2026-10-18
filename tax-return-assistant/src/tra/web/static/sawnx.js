// Sawnx: small conveniences only. Every action also works as a plain form without this file.
"use strict";

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
