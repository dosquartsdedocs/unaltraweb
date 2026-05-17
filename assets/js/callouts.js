(() => {
  const TYPES = ["info", "example", "warning", "objectives", "danger"];
  const DEFAULT_LABELS = {
    ca: {
      info: "NOTA",
      example: "EXEMPLE",
      warning: "ADVERTENCIA",
      objectives: "OBJECTIUS D'APRENENTATGE",
      danger: "ATENCIO",
    },
    es: {
      info: "NOTA",
      example: "EJEMPLO",
      warning: "ADVERTENCIA",
      objectives: "OBJETIVOS DE APRENDIZAJE",
      danger: "ATENCION",
    },
    en: {
      info: "NOTE",
      example: "EXAMPLE",
      warning: "WARNING",
      objectives: "LEARNING OBJECTIVES",
      danger: "CAUTION",
    },
  };

  function currentLang() {
    return (document.documentElement.getAttribute("lang") || "en").toLowerCase().split("-")[0];
  }

  function labelsFor(lang) {
    const siteLabels = window.unaltrawebCalloutLabels || {};
    return siteLabels[lang] || siteLabels.en || DEFAULT_LABELS[lang] || DEFAULT_LABELS.en;
  }

  function blockquoteDepth(blockquote) {
    let depth = 0;
    let parent = blockquote.parentElement;

    while (parent) {
      if (parent.tagName === "BLOCKQUOTE") depth += 1;
      parent = parent.parentElement;
    }

    return depth;
  }

  function removeGeneratedCallouts(scope) {
    scope.querySelectorAll("[data-unaltraweb-callout-title='true']").forEach((title) => title.remove());
    scope.querySelectorAll("blockquote").forEach((blockquote) => {
      blockquote.classList.remove(
        "uw-callout",
        "uw-callout-wrapper",
        "uw-callout-info",
        "uw-callout-example",
        "uw-callout-warning",
        "uw-callout-objectives",
        "uw-callout-danger",
      );
      blockquote.removeAttribute("data-callout");
    });
  }

  function directChildBlockquote(blockquote) {
    return Array.from(blockquote.children).some((child) => child.tagName === "BLOCKQUOTE");
  }

  function firstMeaningfulChild(blockquote) {
    return Array.from(blockquote.children).find((child) => child.nodeType === Node.ELEMENT_NODE);
  }

  function injectTitle(blockquote, label) {
    const firstChild = firstMeaningfulChild(blockquote);
    if (firstChild && firstChild.classList.contains("uw-callout-title")) return;

    const title = document.createElement("p");
    title.className = "uw-callout-title";
    title.dataset.unaltrawebCalloutTitle = "true";
    title.textContent = label;
    blockquote.insertBefore(title, blockquote.firstChild);
  }

  function processCallouts(scope = document) {
    const lang = currentLang();
    const labels = labelsFor(lang);
    const roots = scope.querySelectorAll(".post article, .markdown-section, main, [role='main']");

    roots.forEach((root) => {
      removeGeneratedCallouts(root);

      root.querySelectorAll("blockquote").forEach((blockquote) => {
        if (directChildBlockquote(blockquote)) {
          blockquote.classList.add("uw-callout-wrapper");
          return;
        }

        const depth = blockquoteDepth(blockquote);
        if (depth === 0) return;

        const type = TYPES[Math.min(depth, TYPES.length) - 1] || TYPES[0];
        blockquote.classList.add("uw-callout", `uw-callout-${type}`);
        blockquote.dataset.callout = type;
        injectTitle(blockquote, labels[type] || DEFAULT_LABELS.en[type]);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => processCallouts());
  } else {
    processCallouts();
  }

  document.addEventListener("unaltraweb:contentchange", (event) => processCallouts(event.target || document));
})();
