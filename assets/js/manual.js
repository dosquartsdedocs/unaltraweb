(function () {
  var MIN_SCALE = 0.85;
  var MAX_SCALE = 1.25;
  var STEP = 0.1;
  var searchIndexPromise;

  function normalize(text) {
    return (text || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function slugify(text) {
    return normalize(text).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "section";
  }

  function uniqueId(base, seen) {
    var id = base;
    var index = 2;
    while (document.getElementById(id) || seen[id]) {
      id = base + "-" + index;
      index += 1;
    }
    seen[id] = true;
    return id;
  }

  function applyStoredFontScale() {
    var stored = parseFloat(localStorage.getItem("unaltrawebManualFontScale") || "1");
    if (!Number.isFinite(stored)) stored = 1;
    document.documentElement.style.setProperty("--manual-font-scale", String(stored));
    document.documentElement.style.setProperty("--manual-content-font-size", (1.02 * stored).toFixed(3) + "rem");
    document.documentElement.style.setProperty("--manual-h2-font-size", (1.42 * stored).toFixed(3) + "rem");
    document.documentElement.style.setProperty("--manual-h3-font-size", (1.16 * stored).toFixed(3) + "rem");
  }

  function setupFontControls() {
    applyStoredFontScale();
    document.querySelectorAll("[data-manual-font]").forEach(function (button) {
      if (button.dataset.manualFontReady) return;
      button.dataset.manualFontReady = "true";
      button.addEventListener("click", function () {
        var current = parseFloat(localStorage.getItem("unaltrawebManualFontScale") || "1");
        if (!Number.isFinite(current)) current = 1;
        if (button.dataset.manualFont === "increase") current = Math.min(MAX_SCALE, current + STEP);
        if (button.dataset.manualFont === "decrease") current = Math.max(MIN_SCALE, current - STEP);
        if (button.dataset.manualFont === "reset") current = 1;
        current = Math.round(current * 100) / 100;
        localStorage.setItem("unaltrawebManualFontScale", String(current));
        applyStoredFontScale();
      });
    });
  }

  function addNumbering() {
    var root = document.querySelector(".manual-chapter");
    if (!root) return;
    root.querySelectorAll(".hd-num").forEach(function (node) { node.remove(); });

    var chapter = parseInt(root.getAttribute("data-chapter"), 10);
    if (!Number.isFinite(chapter) || chapter < 1) chapter = 1;
    var section = 0;
    var subsection = 0;

    function prefix(heading, value) {
      var span = document.createElement("span");
      span.className = "hd-num";
      span.textContent = value;
      heading.insertBefore(span, heading.firstChild);
    }

    var title = root.querySelector(".manual-chapter-header h1");
    if (title) prefix(title, String(chapter));

    root.querySelectorAll(".manual-content h2, .manual-content h3").forEach(function (heading) {
      if (heading.tagName.toLowerCase() === "h2") {
        section += 1;
        subsection = 0;
        prefix(heading, chapter + "." + section);
      } else {
        if (section === 0) section = 1;
        subsection += 1;
        prefix(heading, chapter + "." + section + "." + subsection);
      }
    });
  }

  function buildPageToc() {
    var target = document.querySelector("[data-manual-page-toc]");
    var container = document.querySelector("[data-manual-page-toc-container]");
    var content = document.querySelector(".manual-content");
    if (!target || !container || !content) return;

    var headings = Array.prototype.slice.call(content.querySelectorAll("h2, h3"));
    target.innerHTML = "";
    if (!headings.length) {
      container.hidden = true;
      return;
    }

    var seen = {};
    var sections = [];
    var current = null;

    headings.forEach(function (heading) {
      if (!heading.id) heading.id = uniqueId(slugify(heading.textContent), seen);
      var cleanText = heading.textContent.replace(/^\s*\d+(?:\.\d+)*\s*/, "").trim();
      var number = heading.querySelector(".hd-num") ? heading.querySelector(".hd-num").textContent : "";
      var item = { heading: heading, text: (number ? number + " " : "") + cleanText };

      if (heading.tagName.toLowerCase() === "h2" || !current) {
        current = { parent: item, children: [] };
        sections.push(current);
      } else {
        current.children.push(item);
      }
    });

    sections.forEach(function (section) {
      if (!section.children.length) {
        var single = document.createElement("a");
        single.className = "manual-page-toc-link";
        single.href = "#" + section.parent.heading.id;
        single.textContent = section.parent.text;
        target.appendChild(single);
        return;
      }

      var details = document.createElement("details");
      details.className = "manual-page-toc-section";
      details.open = true;
      var summary = document.createElement("summary");
      var link = document.createElement("a");
      link.href = "#" + section.parent.heading.id;
      link.textContent = section.parent.text;
      summary.appendChild(link);
      details.appendChild(summary);

      var list = document.createElement("ol");
      section.children.forEach(function (child) {
        var item = document.createElement("li");
        var sublink = document.createElement("a");
        sublink.href = "#" + child.heading.id;
        sublink.textContent = child.text;
        item.appendChild(sublink);
        list.appendChild(item);
      });
      details.appendChild(list);
      target.appendChild(details);
    });

    container.hidden = false;
  }

  function loadSearchIndex() {
    if (!searchIndexPromise) {
      var url = window.unaltrawebManualSearchUrl || (document.querySelector("base") ? document.querySelector("base").href : "") + "/assets/js/manual-search-index.json";
      searchIndexPromise = fetch(url, { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error("Manual search index unavailable");
        return response.json();
      }).catch(function () { return []; });
    }
    return searchIndexPromise;
  }

  function excerpt(body, query) {
    var source = body || "";
    var low = normalize(source);
    var needle = normalize(query);
    var idx = low.indexOf(needle);
    if (idx < 0) return source.slice(0, 180);
    var start = Math.max(0, idx - 70);
    var end = Math.min(source.length, idx + 170);
    return (start > 0 ? "..." : "") + source.slice(start, end) + (end < source.length ? "..." : "");
  }

  function highlight(text, query) {
    var escaped = (query || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!escaped) return text;
    return text.replace(new RegExp("(" + escaped + ")", "ig"), "<mark>$1</mark>");
  }

  function renderSearchResults(input, entries, query) {
    var box = input.closest(".manual-search");
    if (!box) return;
    var panel = box.querySelector("[data-manual-search-results]");
    var list = box.querySelector("[data-manual-search-list]");
    if (!panel || !list) return;

    list.innerHTML = "";
    if (!query || query.trim().length < 2) {
      panel.hidden = true;
      return;
    }

    var lang = (document.documentElement.getAttribute("lang") || "").toLowerCase();
    var needle = normalize(query);
    var matches = entries.filter(function (entry) {
      if (entry.lang && lang && entry.lang.toLowerCase() !== lang) return false;
      return normalize([entry.title, entry.description, entry.keywords, entry.body].join(" ")).indexOf(needle) !== -1;
    }).slice(0, 12);

    matches.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = entry.url + "?h=" + encodeURIComponent(query);
      link.innerHTML = highlight(entry.title, query);
      var text = document.createElement("p");
      text.innerHTML = highlight(excerpt(entry.body || entry.description || "", query), query);
      item.appendChild(link);
      item.appendChild(text);
      list.appendChild(item);
    });

    if (!matches.length) {
      var empty = document.createElement("li");
      empty.className = "manual-search-empty";
      empty.textContent = "No results";
      list.appendChild(empty);
    }
    panel.hidden = false;
  }

  function setupSearch() {
    document.querySelectorAll("[data-manual-search]").forEach(function (input) {
      if (input.dataset.manualSearchReady) return;
      input.dataset.manualSearchReady = "true";
      var run = function () {
        var query = input.value;
        loadSearchIndex().then(function (entries) { renderSearchResults(input, entries, query); });
      };
      input.addEventListener("input", run);
      input.addEventListener("focus", run);
    });
  }

  function highlightQuery() {
    var params = new URLSearchParams(window.location.search);
    var query = params.get("h");
    if (!query || query.length < 2) return;
    var content = document.querySelector(".manual-content");
    if (!content || content.dataset.manualHighlighted) return;
    content.dataset.manualHighlighted = "true";

    var needle = normalize(query);
    var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        return normalize(node.nodeValue).indexOf(needle) >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var node = walker.nextNode();
    if (node && node.parentNode) {
      var mark = document.createElement("mark");
      mark.className = "manual-search-hit";
      mark.textContent = node.nodeValue;
      node.parentNode.replaceChild(mark, node);
      mark.scrollIntoView({ block: "center" });
    }
  }

  function setupSidebarToggle() {
    document.querySelectorAll("[data-manual-sidebar-toggle]").forEach(function (button) {
      if (button.dataset.manualToggleReady) return;
      button.dataset.manualToggleReady = "true";
      var layout = button.closest(".manual-layout") || document.querySelector(".manual-layout");
      if (!layout) return;
      var collapsed = localStorage.getItem("unaltrawebManualSidebarCollapsed") === "true";
      layout.classList.toggle("manual-sidebar-collapsed", collapsed);
      button.setAttribute("aria-expanded", collapsed ? "false" : "true");
      button.addEventListener("click", function () {
        var nowCollapsed = layout.classList.toggle("manual-sidebar-collapsed");
        localStorage.setItem("unaltrawebManualSidebarCollapsed", nowCollapsed ? "true" : "false");
        button.setAttribute("aria-expanded", nowCollapsed ? "false" : "true");
      });
    });
  }

  function enhanceManual() {
    setupSidebarToggle();
    setupFontControls();
    addNumbering();
    buildPageToc();
    setupSearch();
    highlightQuery();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceManual);
  } else {
    enhanceManual();
  }
  document.addEventListener("unaltraweb:contentchange", enhanceManual);
})();
