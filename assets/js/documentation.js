(function () {
  var MIN_SCALE = 0.85;
  var MAX_SCALE = 1.25;
  var STEP = 0.1;
  var STORAGE_KEY = "unaltrawebDocumentationFontScale";

  function readScale() {
    var stored = parseFloat(localStorage.getItem(STORAGE_KEY) || "1");
    return Number.isFinite(stored) ? stored : 1;
  }

  function applyStoredFontScale() {
    var scale = readScale();
    document.documentElement.style.setProperty("--documentation-font-scale", String(scale));
    document.documentElement.style.setProperty("--documentation-content-font-size", (1.02 * scale).toFixed(3) + "rem");
    document.documentElement.style.setProperty("--documentation-h2-font-size", (1.45 * scale).toFixed(3) + "rem");
    document.documentElement.style.setProperty("--documentation-h3-font-size", (1.18 * scale).toFixed(3) + "rem");
  }

  function setupFontControls() {
    applyStoredFontScale();
    document.querySelectorAll("[data-documentation-font]").forEach(function (button) {
      if (button.dataset.documentationFontReady) return;
      button.dataset.documentationFontReady = "true";
      button.addEventListener("click", function () {
        var scale = readScale();
        if (button.dataset.documentationFont === "increase") scale = Math.min(MAX_SCALE, scale + STEP);
        if (button.dataset.documentationFont === "decrease") scale = Math.max(MIN_SCALE, scale - STEP);
        if (button.dataset.documentationFont === "reset") scale = 1;
        scale = Math.round(scale * 100) / 100;
        localStorage.setItem(STORAGE_KEY, String(scale));
        applyStoredFontScale();
      });
    });
  }

  function themeSetting() {
    return document.documentElement.getAttribute("data-theme-setting") || localStorage.getItem("theme") || "system";
  }

  function updateThemeLabels() {
    document.querySelectorAll("[data-documentation-theme-label]").forEach(function (label) {
      var button = label.closest("[data-theme-label-system]");
      if (!button) return;
      var setting = themeSetting();
      var attr = "themeLabel" + setting.charAt(0).toUpperCase() + setting.slice(1);
      label.textContent = button.dataset[attr] || setting;
    });
  }

  function setupDocumentationTree() {
    document.querySelectorAll("[data-documentation-tree]").forEach(function (tree) {
      if (tree.dataset.documentationTreeReady) return;
      tree.dataset.documentationTreeReady = "true";
      var storageKey = "unaltrawebDocumentationTree:" + window.location.pathname.split("/").slice(0, -1).join("/");
      var stored = {};
      try {
        stored = JSON.parse(localStorage.getItem(storageKey) || "{}");
      } catch (error) {
        stored = {};
      }

      tree.querySelectorAll("details[data-documentation-tree-id]").forEach(function (details) {
        var id = details.dataset.documentationTreeId;
        var hasActive = details.querySelector(".active") !== null;
        if (Object.prototype.hasOwnProperty.call(stored, id)) {
          details.open = stored[id];
        }
        if (hasActive) details.open = true;
        details.addEventListener("toggle", function () {
          stored[id] = details.open;
          localStorage.setItem(storageKey, JSON.stringify(stored));
        });
      });
    });
  }

  function enhanceDocumentation() {
    setupFontControls();
    updateThemeLabels();
    setupDocumentationTree();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceDocumentation);
  } else {
    enhanceDocumentation();
  }
  document.addEventListener("unaltraweb:contentchange", enhanceDocumentation);
  document.addEventListener("unaltraweb:themechange", updateThemeLabels);
})();
