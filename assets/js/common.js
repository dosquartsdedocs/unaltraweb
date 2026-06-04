$(document).ready(function () {
  // add toggle functionality to publication detail buttons
  $("a.abstract").click(function () {
    $(this).parent().parent().find(".cite.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".abstract.hidden").toggleClass("open");
    $(this).parent().parent().find(".award.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden.open").toggleClass("open");
  });
  $("a.cite").click(function () {
    $(this).parent().parent().find(".abstract.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".award.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".cite.hidden").toggleClass("open");
  });
  $("a.award").click(function () {
    $(this).parent().parent().find(".cite.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".abstract.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".award.hidden").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden.open").toggleClass("open");
  });
  $("a.bibtex").click(function () {
    $(this).parent().parent().find(".cite.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".abstract.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".award.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden").toggleClass("open");
  });
  $("a.openalex").click(function () {
    $(this).parent().parent().find(".cite.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".abstract.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".award.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden").toggleClass("open");
  });
  $("a.scimago").click(function () {
    $(this).parent().parent().find(".cite.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".abstract.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".award.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".bibtex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".openalex.hidden.open").toggleClass("open");
    $(this).parent().parent().find(".scimago.hidden").toggleClass("open");
  });

  function closeReadingBiblioPanels() {
    $(".reading-biblio-panel.hidden.open").removeClass("open");
  }

  $(document).on("click", "[data-reading-biblio-close]", function () {
    $(this).closest(".reading-biblio-panel").removeClass("open");
  });

  $(document).on("click", function (event) {
    if (!$(".reading-biblio-panel.hidden.open").length) return;
    if ($(event.target).closest(".reading-biblio-panel, .reading-biblio-actions").length) return;
    closeReadingBiblioPanels();
  });

  $(document).on("keydown", function (event) {
    if (event.key === "Escape") closeReadingBiblioPanels();
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
