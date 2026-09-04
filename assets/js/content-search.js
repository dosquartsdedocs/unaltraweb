(function () {
  "use strict";

  var matcher = window.UnaltrawebContentSearchMatch;
  var searchIndexPromises = {};
  var DOCUMENTATION_PROFILE_STORAGE_KEY = "unaltrawebDocumentationProfile";
  var DOCUMENTATION_PROFILE_PARAM = "doc_profile";
  var MAX_RENDERED_RESULTS = 24;
  var MAX_QUERY_LENGTH = 120;
  var BLOCK_TAGS = ["address", "article", "aside", "blockquote", "div", "dl", "dt", "dd", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul"];
  var DYNAMIC_SOURCE_CLASSES = ["language-mermaid", "language-vega_lite", "language-plotly", "language-echarts", "language-geojson", "language-diff2html"];

  if (!matcher) return;

  function defaultSearchUrl() {
    var input = document.querySelector("[data-content-search]");
    if (input && input.dataset.contentSearchUrl) return input.dataset.contentSearchUrl;
    if (window.unaltrawebContentSearchUrl) return window.unaltrawebContentSearchUrl;
    return "/assets/js/content-search-index.json";
  }

  function loadSearchIndex(url) {
    var resolvedUrl = url || defaultSearchUrl();
    if (!searchIndexPromises[resolvedUrl]) {
      searchIndexPromises[resolvedUrl] = fetch(resolvedUrl, { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error("Content search index unavailable");
        return response.json();
      }).catch(function () { return []; });
    }
    return searchIndexPromises[resolvedUrl];
  }

  function normalizeProfileToken(value) {
    return (value || "").toString().trim().toLowerCase();
  }

  function storedDocumentationProfile() {
    try {
      return localStorage.getItem(DOCUMENTATION_PROFILE_STORAGE_KEY);
    } catch (_error) {
      return "";
    }
  }

  function readDocumentationProfile() {
    var switcher = document.querySelector("[data-documentation-profile-switcher]");
    if (!switcher) return "";
    var params = new URLSearchParams(window.location.search);
    var profile = params.has(DOCUMENTATION_PROFILE_PARAM)
      ? normalizeProfileToken(params.get(DOCUMENTATION_PROFILE_PARAM))
      : normalizeProfileToken(storedDocumentationProfile());
    if (!profile) return "";
    var hasProfileOption = Array.prototype.slice.call(switcher.querySelectorAll("[data-documentation-profile-select] option")).some(function (option) {
      return normalizeProfileToken(option.value) === profile;
    });
    return hasProfileOption ? profile : "";
  }

  function documentationSearchProfileEnabled() {
    return (document.documentElement.getAttribute("data-site-profile") || "") === "unaltredocs";
  }

  function entryMatchesDocumentationProfile(entry, activeProfile) {
    if (!activeProfile) return true;
    var profiles = entry && Array.isArray(entry.documentation_profile_slugs) ? entry.documentation_profile_slugs : [];
    return profiles.length === 0 || profiles.indexOf(activeProfile) !== -1;
  }

  function filteredEntries(entries) {
    var lang = (document.documentElement.getAttribute("lang") || "").toLowerCase();
    var activeProfile = documentationSearchProfileEnabled() ? readDocumentationProfile() : "";
    return entries.filter(function (entry) {
      if (entry.lang && lang && entry.lang.toLowerCase() !== lang) return false;
      return !activeProfile || entryMatchesDocumentationProfile(entry, activeProfile);
    });
  }

  function occurrenceResults(entries, query) {
    var pageResultSets = [];
    filteredEntries(entries).forEach(function (entry) {
      var pageResults = [];
      var segments = Array.isArray(entry.segments) && entry.segments.length ? entry.segments : [entry.body || ""];
      segments.forEach(function (source) {
        matcher.findOccurrences(source, query).forEach(function (occurrence) {
          pageResults.push({
            source: source,
            entry: entry,
            occurrence: occurrence
          });
        });
      });
      pageResults.forEach(function (result, index) {
        Object.assign(result, {
          entry: entry,
          occurrenceNumber: index + 1,
          pageOccurrenceTotal: pageResults.length
        });
      });
      if (pageResults.length) pageResultSets.push(pageResults);
    });
    var results = [];
    for (var occurrenceIndex = 0; pageResultSets.some(function (pageResults) { return occurrenceIndex < pageResults.length; }); occurrenceIndex += 1) {
      pageResultSets.forEach(function (pageResults) {
        if (pageResults[occurrenceIndex]) results.push(pageResults[occurrenceIndex]);
      });
    }
    return results;
  }

  function searchBox(input) {
    return input.closest("[data-content-search-box]") || input.parentElement;
  }

  function setPanelOpen(input, panel, open) {
    panel.hidden = !open;
    input.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function resultUrl(value, query, occurrenceNumber) {
    var target;
    try {
      target = new URL(value || "#", window.location.origin);
    } catch (_error) {
      return "#";
    }
    if (target.origin !== window.location.origin) return "#";
    target.searchParams.set("h", query);
    target.searchParams.set("hit", occurrenceNumber.toString());
    var current = new URLSearchParams(window.location.search);
    if (current.has(DOCUMENTATION_PROFILE_PARAM) && !target.searchParams.has(DOCUMENTATION_PROFILE_PARAM)) {
      target.searchParams.set(DOCUMENTATION_PROFILE_PARAM, current.get(DOCUMENTATION_PROFILE_PARAM));
    }
    return target.pathname + target.search + target.hash;
  }

  function entryMeta(entry) {
    return [entry.section, entry.subsection].filter(Boolean).join(" / ");
  }

  function formatLabel(template, current, total) {
    return (template || "Match {current} of {total}")
      .replace("{current}", current.toString())
      .replace("{total}", total.toString());
  }

  function appendExcerpt(parent, body, occurrence) {
    var parts = matcher.excerptParts(body, occurrence);
    parent.appendChild(document.createTextNode(parts.before));
    var mark = document.createElement("mark");
    mark.textContent = parts.match;
    parent.appendChild(mark);
    parent.appendChild(document.createTextNode(parts.after));
  }

  function renderSearchResults(input, entries, query) {
    var box = searchBox(input);
    if (!box) return;
    var panel = box.querySelector("[data-content-search-results]");
    var list = box.querySelector("[data-content-search-list]");
    if (!panel || !list) return;

    query = (query || "").toString().slice(0, MAX_QUERY_LENGTH);
    list.replaceChildren();
    if (!query || query.trim().length < 2) {
      setPanelOpen(input, panel, false);
      return;
    }

    var matches = occurrenceResults(entries, query);
    matches.slice(0, MAX_RENDERED_RESULTS).forEach(function (result) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = resultUrl(result.entry.url, query, result.occurrenceNumber);
      link.textContent = result.entry.title;
      item.appendChild(link);

      var metaParts = [entryMeta(result.entry), formatLabel(
        input.dataset.contentSearchMatch,
        result.occurrenceNumber,
        result.pageOccurrenceTotal
      )].filter(Boolean);
      var meta = document.createElement("small");
      meta.className = "content-search-meta";
      meta.textContent = metaParts.join(" / ");
      item.appendChild(meta);

      var text = document.createElement("p");
      appendExcerpt(text, result.source, result.occurrence);
      item.appendChild(text);
      list.appendChild(item);
    });

    if (!matches.length) {
      var empty = document.createElement("li");
      empty.className = "content-search-empty";
      empty.textContent = input.dataset.contentSearchEmpty || panel.dataset.contentSearchEmpty || "No results";
      list.appendChild(empty);
    }
    setPanelOpen(input, panel, true);
  }

  function setupSearch() {
    document.querySelectorAll("[data-content-search]").forEach(function (input) {
      if (input.dataset.contentSearchReady) return;
      input.dataset.contentSearchReady = "true";
      var run = function () {
        var query = input.value;
        loadSearchIndex(input.dataset.contentSearchUrl).then(function (entries) {
          renderSearchResults(input, entries, query);
        });
      };
      input.addEventListener("input", run);
      input.addEventListener("focus", run);
      input.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        var box = searchBox(input);
        var panel = box && box.querySelector("[data-content-search-results]");
        if (panel) setPanelOpen(input, panel, false);
      });
    });
  }

  function closeSearchPanels(event) {
    document.querySelectorAll("[data-content-search-box]").forEach(function (box) {
      if (box.contains(event.target)) return;
      var input = box.querySelector("[data-content-search]");
      var panel = box.querySelector("[data-content-search-results]");
      if (input && panel) setPanelOpen(input, panel, false);
    });
  }

  function rerenderSearchResults() {
    document.querySelectorAll("[data-content-search]").forEach(function (input) {
      if (!input.dataset.contentSearchReady || !input.value || input.value.trim().length < 2) return;
      loadSearchIndex(input.dataset.contentSearchUrl).then(function (entries) {
        renderSearchResults(input, entries, input.value);
      });
    });
  }

  function contentRoot() {
    var configured = window.unaltrawebContentSearchTarget;
    var configuredRoot = configured ? document.querySelector(configured) : null;
    if (configuredRoot) return configuredRoot;
    var input = document.querySelector("[data-content-search-target]");
    var inputRoot = input && input.dataset.contentSearchTarget ? document.querySelector(input.dataset.contentSearchTarget) : null;
    if (inputRoot) return inputRoot;
    return document.querySelector("[data-content-search-root], .manual-content, .documentation-content");
  }

  function dynamicSource(element) {
    return element.tagName.toLowerCase() === "code" && DYNAMIC_SOURCE_CLASSES.some(function (className) {
      return element.classList.contains(className);
    });
  }

  function excludedElement(element) {
    return element.matches("script, style, template, noscript, textarea, input, select, button, nav, [hidden], [inert], [aria-hidden='true'], .content-search-navigation, .documentation-index, .mermaid, .vega-lite, .echarts, .map, .diff2html, .js-plotly-plot") || dynamicSource(element);
  }

  function searchableTextStream(content) {
    var rawText = "";
    var rawRanges = [];

    function appendSpace() {
      if (rawText && !/\s$/u.test(rawText)) rawText += " ";
    }

    function visit(node) {
      Array.prototype.forEach.call(node.childNodes, function (child) {
        if (child.nodeType === Node.TEXT_NODE) {
          if (!child.nodeValue) return;
          var start = rawText.length;
          rawText += child.nodeValue;
          rawRanges.push({ node: child, start: start, end: rawText.length });
          return;
        }
        if (child.nodeType !== Node.ELEMENT_NODE || excludedElement(child)) return;
        var tagName = child.tagName.toLowerCase();
        var block = BLOCK_TAGS.indexOf(tagName) !== -1 || tagName === "br";
        if (block) appendSpace();
        if (tagName !== "br") visit(child);
        if (block) appendSpace();
      });
    }

    visit(content);
    var collapsed = matcher.collapseWhitespaceWithMap(rawText);
    return { text: collapsed.text, ranges: rawRanges, starts: collapsed.starts, ends: collapsed.ends };
  }

  function markContentOccurrences(content, query, requestedHit) {
    var stream = searchableTextStream(content);
    var occurrences = matcher.findOccurrences(stream.text, query);
    if (!occurrences.length) return null;
    var groups = [];
    occurrences.forEach(function (occurrence, occurrenceIndex) {
      var rawOccurrenceStart = stream.starts[occurrence.start];
      var rawOccurrenceEnd = stream.ends[occurrence.end - 1];
      stream.ranges.forEach(function (range) {
        var overlapStart = Math.max(rawOccurrenceStart, range.start);
        var overlapEnd = Math.min(rawOccurrenceEnd, range.end);
        if (overlapStart >= overlapEnd) return;
        var localStart = overlapStart - range.start;
        var localEnd = overlapEnd - range.start;
        while (localStart < localEnd && /\s/u.test(range.node.nodeValue[localStart])) localStart += 1;
        while (localEnd > localStart && /\s/u.test(range.node.nodeValue[localEnd - 1])) localEnd -= 1;
        if (localStart >= localEnd) return;
        var group = groups.find(function (candidate) { return candidate.node === range.node; });
        if (!group) {
          group = { node: range.node, parts: [] };
          groups.push(group);
        }
        group.parts.push({
          start: localStart,
          end: localEnd,
          hitNumber: occurrenceIndex + 1
        });
      });
    });

    var activeHit = Math.min(Math.max(requestedHit, 1), occurrences.length);
    var activeMark = null;
    groups.forEach(function (group) {
      var fragment = document.createDocumentFragment();
      var cursor = 0;
      group.parts.forEach(function (part) {
        fragment.appendChild(document.createTextNode(group.node.nodeValue.slice(cursor, part.start)));
        var mark = document.createElement("mark");
        mark.className = "content-search-hit";
        mark.textContent = group.node.nodeValue.slice(part.start, part.end);
        if (part.hitNumber === activeHit) {
          mark.classList.add("content-search-hit-active");
          if (!activeMark) {
            mark.setAttribute("aria-current", "true");
            mark.setAttribute("tabindex", "-1");
            activeMark = mark;
          }
        }
        fragment.appendChild(mark);
        cursor = part.end;
      });
      fragment.appendChild(document.createTextNode(group.node.nodeValue.slice(cursor)));
      group.node.parentNode.replaceChild(fragment, group.node);
    });
    return { activeHit: activeHit, activeMark: activeMark, total: occurrences.length };
  }

  function revealActiveOccurrence(mark) {
    var ancestor = mark && mark.parentElement;
    while (ancestor) {
      if (ancestor.tagName && ancestor.tagName.toLowerCase() === "details") ancestor.open = true;
      if (ancestor.classList.contains("hidden")) ancestor.classList.add("open");
      if (ancestor.classList.contains("collapse")) ancestor.classList.add("show");
      if (ancestor.classList.contains("unloaded")) ancestor.classList.remove("unloaded");
      if (ancestor.tagName && ancestor.tagName.toLowerCase() === "li" && ancestor.parentElement && ancestor.parentElement.classList.contains("tab-content")) {
        ancestor.classList.add("active");
      }
      ancestor = ancestor.parentElement;
    }
  }

  function normalizedPath(value) {
    var url = new URL(value, window.location.origin);
    return url.pathname.replace(/index\.html$/, "").replace(/\/$/, "") || "/";
  }

  function addNavigationLink(container, className, label, result, query) {
    if (!result) return;
    var link = document.createElement("a");
    link.className = className;
    link.href = resultUrl(result.entry.url, query, result.occurrenceNumber);
    link.textContent = label;
    container.appendChild(link);
  }

  function addOccurrenceNavigation(content, entries, query, marked, input) {
    var results = occurrenceResults(entries, query);
    var currentPath = normalizedPath(window.location.href);
    var resultIndex = results.findIndex(function (result) {
      return normalizedPath(result.entry.url) === currentPath && result.occurrenceNumber === marked.activeHit;
    });
    var current = resultIndex >= 0 ? resultIndex + 1 : marked.activeHit;
    var total = resultIndex >= 0 ? results.length : marked.total;
    var navigation = document.createElement("nav");
    navigation.className = "content-search-navigation";
    navigation.setAttribute("aria-label", input.dataset.contentSearchResultsLabel || "Search results");

    var status = document.createElement("span");
    status.className = "content-search-navigation-status";
    status.setAttribute("aria-live", "polite");
    status.textContent = formatLabel(input.dataset.contentSearchMatch, current, total);
    navigation.appendChild(status);

    var links = document.createElement("span");
    links.className = "content-search-navigation-links";
    if (resultIndex >= 0) {
      addNavigationLink(links, "content-search-previous", input.dataset.contentSearchPrevious || "Previous match", results[resultIndex - 1], query);
      addNavigationLink(links, "content-search-next", input.dataset.contentSearchNext || "Next match", results[resultIndex + 1], query);
    }
    navigation.appendChild(links);
    content.insertBefore(navigation, content.firstChild);
  }

  function highlightQuery() {
    var params = new URLSearchParams(window.location.search);
    var query = (params.get("h") || "").slice(0, MAX_QUERY_LENGTH);
    if (!query || query.trim().length < 2) return;
    var content = contentRoot();
    if (!content || content.dataset.contentSearchHighlighted) return;
    content.dataset.contentSearchHighlighted = "true";

    var requestedHit = parseInt(params.get("hit") || "1", 10);
    var marked = markContentOccurrences(content, query, Number.isFinite(requestedHit) ? requestedHit : 1);
    if (!marked) return;
    var input = document.querySelector("[data-content-search]");
    if (input) {
      loadSearchIndex(input.dataset.contentSearchUrl).then(function (entries) {
        addOccurrenceNavigation(content, entries, query, marked, input);
      });
    }
    revealActiveOccurrence(marked.activeMark);
    var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    marked.activeMark.scrollIntoView({ block: "center", behavior: reducedMotion ? "auto" : "smooth" });
    marked.activeMark.focus({ preventScroll: true });
  }

  function enhanceContentSearch() {
    setupSearch();
    highlightQuery();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceContentSearch);
  } else {
    enhanceContentSearch();
  }
  document.addEventListener("click", closeSearchPanels);
  document.addEventListener("unaltraweb:contentchange", enhanceContentSearch);
  document.addEventListener("unaltraweb:documentationprofilechange", rerenderSearchResults);
})();
