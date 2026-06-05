$(document).ready(function () {
  // add toggle functionality to publication detail buttons
  const biblioPanelClasses = ["cite", "abstract", "award", "bibtex", "openalex", "scimago"];

  function updateBiblioButtonState($entry) {
    biblioPanelClasses.forEach(function (panelClass) {
      const isOpen = $entry.find(`.${panelClass}.hidden.open`).length > 0;
      $entry.find(`.links a.${panelClass}.btn`).toggleClass("biblio-active", isOpen).attr("aria-expanded", isOpen ? "true" : "false");
    });
  }

  function toggleBiblioPanel(link, panelClass) {
    const $entry = $(link).parent().parent();
    const panelSelector = `.${panelClass}.hidden`;

    biblioPanelClasses.forEach(function (otherPanelClass) {
      if (otherPanelClass !== panelClass) $entry.find(`.${otherPanelClass}.hidden.open`).removeClass("open");
    });

    $entry.find(panelSelector).toggleClass("open");
    updateBiblioButtonState($entry);
  }

  $("a.abstract").click(function () {
    toggleBiblioPanel(this, "abstract");
  });
  $("a.cite").click(function () {
    toggleBiblioPanel(this, "cite");
  });
  $("a.award").click(function () {
    toggleBiblioPanel(this, "award");
  });
  $("a.bibtex").click(function () {
    toggleBiblioPanel(this, "bibtex");
  });
  $("a.openalex").click(function () {
    toggleBiblioPanel(this, "openalex");
  });
  $("a.scimago").click(function () {
    toggleBiblioPanel(this, "scimago");
  });

  $(document).on("click", "[data-copy-target]", function () {
    const button = this;
    const target = document.querySelector(button.getAttribute("data-copy-target"));
    if (!target) return;
    const text = target.innerText.trim();
    const doneLabel = button.getAttribute("data-copy-done") || "Copied";
    const copyLabel = button.getAttribute("data-copy-label") || button.innerText;
    const markCopied = function () {
      button.innerText = doneLabel;
      window.setTimeout(function () {
        button.innerText = copyLabel;
      }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(markCopied).catch(function () {});
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
      markCopied();
    } finally {
      document.body.removeChild(textarea);
    }
  });

  $("a").removeClass("waves-effect waves-light");

  // bootstrap-toc
  if ($("#toc-sidebar").length) {
    // remove related publications years from the TOC
    $(".publications h2").each(function () {
      $(this).attr("data-toc-skip", "");
    });
    var navSelector = "#toc-sidebar";
    var $myNav = $(navSelector);
    Toc.init($myNav);
    $("body").scrollspy({
      target: navSelector,
      offset: 100,
    });
  }

  // add css to jupyter notebooks
  const cssLink = document.createElement("link");
  cssLink.href = "../css/jupyter.css";
  cssLink.rel = "stylesheet";
  cssLink.type = "text/css";

  let jupyterTheme = determineComputedTheme();

  $(".jupyter-notebook-iframe-container iframe").each(function () {
    $(this).contents().find("head").append(cssLink);

    if (jupyterTheme == "dark") {
      $(this).bind("load", function () {
        $(this).contents().find("body").attr({
          "data-jp-theme-light": "false",
          "data-jp-theme-name": "JupyterLab Dark",
        });
      });
    }
  });

  // trigger popovers
  $('[data-toggle="popover"]').popover({
    trigger: "hover",
  });
});
