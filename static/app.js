// EvalPro AI — small progressive-enhancement helpers (no build step, no deps)

document.addEventListener("DOMContentLoaded", function () {
  // Auto-dismiss flash messages after a few seconds
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 5000);
  });

  // Dropzone: click-to-browse already works via the transparent file input;
  // this adds drag styling and a filename preview.
  var dropzone = document.querySelector(".dropzone");
  if (dropzone) {
    var input = dropzone.querySelector('input[type="file"]');
    var filenameEl = dropzone.querySelector(".dz-filename");

    function showFilename(file) {
      if (file) {
        filenameEl.textContent = "Selected: " + file.name;
        dropzone.classList.add("has-file");
      } else {
        dropzone.classList.remove("has-file");
      }
    }

    input.addEventListener("change", function () {
      showFilename(input.files && input.files[0]);
    });

    ["dragenter", "dragover"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      });
    });
    dropzone.addEventListener("drop", function (e) {
      var files = e.dataTransfer.files;
      if (files && files.length) {
        input.files = files;
        showFilename(files[0]);
      }
    });
  }

  // Show a loading overlay while the evaluation form submits
  // (OCR + semantic similarity can take a couple of seconds).
  var evalForm = document.querySelector("form[data-loading-message]");
  var overlay = document.getElementById("loading-overlay");
  if (evalForm && overlay) {
    evalForm.addEventListener("submit", function (e) {
      if (!evalForm.checkValidity()) return; // let native validation show first
      overlay.classList.add("active");
      var btn = evalForm.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = "Evaluating…"; }
    });
  }

  // ----- Confirm modal for destructive forms ([data-confirm-title]) -----
  var modal = document.getElementById("confirm-modal");
  if (modal) {
    var pendingForm = null;
    var titleEl = document.getElementById("confirm-title");
    var bodyEl = document.getElementById("confirm-body");
    var lastFocus = null;

    function openModal(form) {
      pendingForm = form;
      lastFocus = document.activeElement;
      titleEl.textContent = form.dataset.confirmTitle || "Are you sure?";
      bodyEl.textContent = form.dataset.confirmBody || "This cannot be undone.";
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
      modal.querySelector("[data-modal-cancel]").focus();
    }
    function closeModal() {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      pendingForm = null;
      if (lastFocus) lastFocus.focus();
    }

    document.querySelectorAll("form[data-confirm-title]").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        if (f.dataset.confirmed === "1") return;
        e.preventDefault();
        openModal(f);
      });
    });
    modal.querySelector("[data-modal-cancel]").addEventListener("click", closeModal);
    modal.querySelector("[data-modal-confirm]").addEventListener("click", function () {
      if (!pendingForm) return;
      pendingForm.dataset.confirmed = "1";
      pendingForm.submit();
    });
    modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains("open")) closeModal();
    });
  }

  // ----- Dashboard: select all, bulk-delete state, search -----
  var table = document.getElementById("results-table");
  if (table) {
    var selectAll = document.getElementById("select-all");
    var checks = Array.prototype.slice.call(table.querySelectorAll(".row-check"));
    var bulkBtn = document.getElementById("bulk-delete");
    var selCount = document.getElementById("sel-count");
    var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
    var rowCount = document.getElementById("row-count");
    var noMatch = document.getElementById("no-match");

    function visibleChecks() {
      return checks.filter(function (c) { return !c.closest("tr").hidden; });
    }
    function refreshSelection() {
      var n = checks.filter(function (c) { return c.checked; }).length;
      bulkBtn.disabled = n === 0;
      selCount.textContent = n ? "(" + n + ")" : "";
      var vis = visibleChecks();
      selectAll.checked = vis.length > 0 && vis.every(function (c) { return c.checked; });
      selectAll.indeterminate = !selectAll.checked && vis.some(function (c) { return c.checked; });
      checks.forEach(function (c) { c.closest("tr").classList.toggle("selected", c.checked); });
    }
    selectAll.addEventListener("change", function () {
      visibleChecks().forEach(function (c) { c.checked = selectAll.checked; });
      refreshSelection();
    });
    checks.forEach(function (c) { c.addEventListener("change", refreshSelection); });

    var search = document.getElementById("table-search");
    if (search) {
      search.addEventListener("input", function () {
        var q = search.value.trim().toLowerCase();
        var shown = 0;
        rows.forEach(function (tr) {
          var match = !q || tr.dataset.name.indexOf(q) !== -1;
          tr.hidden = !match;
          if (match) shown++;
        });
        rowCount.textContent = q ? shown + " of " + rows.length : rows.length + " total";
        noMatch.hidden = shown !== 0;
        refreshSelection();
      });
    }
    refreshSelection();
  }
});
