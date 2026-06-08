(function () {
  var searchIndexPromises = {};
  var DOCUMENTATION_PROFILE_STORAGE_KEY = "unaltrawebDocumentationProfile";
  var DOCUMENTATION_PROFILE_PARAM = "doc_profile";

  function normalize(text) {
    return (text || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function defaultSearchUrl() {
    if (window.unaltrawebContentSearchUrl) return window.unaltrawebContentSearchUrl;
    if (window.unaltrawebManualSearchUrl) return window.unaltrawebManualSearchUrl;
    return (document.querySelector("base") ? document.querySelector("base").href : "") + "/assets/js/content-search-index.json";
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

  function readDocumentationProfile() {
    var switcher = document.querySelector("[data-documentation-profile-switcher]");
    if (!switcher) return "";
    var params = new URLSearchParams(window.location.search);
    var profile = params.has(DOCUMENTATION_PROFILE_PARAM)
      ? normalizeProfileToken(params.get(DOCUMENTATION_PROFILE_PARAM))
      : normalizeProfileToken(localStorage.getItem(DOCUMENTATION_PROFILE_STORAGE_KEY));
    if (!profile) return "";
    var hasProfileOption = Array.prototype.slice.call(switcher.querySelectorAll("[data-documentation-profile-select] option")).some(function (option) {
      return normalizeProfileToken(option.value) === profile;
    });
    return hasProfileOption ? profile : "";
  }

  function documentationSearchProfileEnabled(input) {
    var siteProfile = document.documentElement.getAttribute("data-site-profile") || "";
    var url = input && input.dataset ? input.dataset.contentSearchUrl || "" : "";
    return siteProfile === "unaltredocs" && url.indexOf("documentation-search-index") !== -1;
  }

  function entryMatchesDocumentationProfile(entry, activeProfile) {
    if (!activeProfile) return true;
    var profiles = entry && Array.isArray(entry.documentation_profile_slugs) ? entry.documentation_profile_slugs : [];
    return profiles.length === 0 || profiles.indexOf(activeProfile) !== -1;
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

  function escapeHtml(text) {
    var node = document.createElement("span");
    node.textContent = text || "";
    return node.innerHTML;
  }

  function highlight(text, query) {
    var safeText = escapeHtml(text);
    var escaped = escapeHtml(query || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!escaped) return safeText;
    return safeText.replace(new RegExp("(" + escaped + ")", "ig"), "<mark>$1</mark>");
  }

  function searchBox(input) {
    return input.closest("[data-content-search-box]") || input.closest(".content-search") || input.closest(".manual-search") || input.parentElement;
  }

  function resultUrl(url, query) {
    var parts = (url || "#").split("#");
    var base = parts.shift() || "#";
    var hash = parts.length ? "#" + parts.join("#") : "";
    var separator = base.indexOf("?") >= 0 ? "&" : "?";
    return base + separator + "h=" + encodeURIComponent(query) + hash;
  }

  function entryMeta(entry) {
    return [entry.section, entry.subsection].filter(Boolean).join(" / ");
  }

  function renderSearchResults(input, entries, query) {
    var box = searchBox(input);
    if (!box) return;
    var panel = box.querySelector("[data-content-search-results]");
    var list = box.querySelector("[data-content-search-list]");
    if (!panel || !list) return;

    list.innerHTML = "";
    if (!query || query.trim().length < 2) {
      panel.hidden = true;
      return;
    }

    var lang = (document.documentElement.getAttribute("lang") || "").toLowerCase();
    var needle = normalize(query);
    var activeProfile = documentationSearchProfileEnabled(input) ? readDocumentationProfile() : "";
    var matches = entries.filter(function (entry) {
      if (entry.lang && lang && entry.lang.toLowerCase() !== lang) return false;
      if (activeProfile && !entryMatchesDocumentationProfile(entry, activeProfile)) return false;
      return normalize([entry.title, entry.description, entry.keywords, entry.section, entry.subsection, entry.body].join(" ")).indexOf(needle) !== -1;
    }).slice(0, 12);

    matches.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = resultUrl(entry.url, query);
      link.innerHTML = highlight(entry.title, query);
      item.appendChild(link);

      var metaText = entryMeta(entry);
      if (metaText) {
        var meta = document.createElement("small");
        meta.className = "content-search-meta";
        meta.textContent = metaText;
        item.appendChild(meta);
      }

      var text = document.createElement("p");
      text.innerHTML = highlight(excerpt(entry.body || entry.description || "", query), query);
      item.appendChild(text);
      list.appendChild(item);
    });

    if (!matches.length) {
      var empty = document.createElement("li");
      empty.className = "content-search-empty";
      empty.textContent = input.dataset.contentSearchEmpty || panel.dataset.contentSearchEmpty || "No results";
      list.appendChild(empty);
    }
    panel.hidden = false;
  }

  function setupSearch() {
    document.querySelectorAll("[data-content-search]").forEach(function (input) {
      if (input.dataset.contentSearchReady) return;
      input.dataset.contentSearchReady = "true";
      var run = function () {
        var query = input.value;
        loadSearchIndex(input.dataset.contentSearchUrl).then(function (entries) { renderSearchResults(input, entries, query); });
      };
      input.addEventListener("input", run);
      input.addEventListener("focus", run);
    });
  }

  function rerenderSearchResults() {
    document.querySelectorAll("[data-content-search]").forEach(function (input) {
      if (!input.dataset.contentSearchReady) return;
      var query = input.value;
      if (!query || query.trim().length < 2) return;
      loadSearchIndex(input.dataset.contentSearchUrl).then(function (entries) { renderSearchResults(input, entries, query); });
    });
  }

  function contentRoot() {
    var configured = window.unaltrawebContentSearchTarget;
    if (configured) return document.querySelector(configured);
    var input = document.querySelector("[data-content-search-target]");
    if (input && input.dataset.contentSearchTarget) return document.querySelector(input.dataset.contentSearchTarget);
    return document.querySelector(".manual-content, .documentation-content");
  }

  function highlightQuery() {
    var params = new URLSearchParams(window.location.search);
    var query = params.get("h");
    if (!query || query.length < 2) return;
    var content = contentRoot();
    if (!content || content.dataset.contentSearchHighlighted) return;
    content.dataset.contentSearchHighlighted = "true";

    var needle = normalize(query);
    var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var parentTag = node.parentNode && node.parentNode.tagName ? node.parentNode.tagName.toLowerCase() : "";
        if (["script", "style", "textarea", "input"].indexOf(parentTag) >= 0) return NodeFilter.FILTER_REJECT;
        return normalize(node.nodeValue).indexOf(needle) >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var node = walker.nextNode();
    if (node && node.parentNode) {
      var mark = document.createElement("mark");
      mark.className = "content-search-hit";
      mark.textContent = node.nodeValue;
      node.parentNode.replaceChild(mark, node);
      mark.scrollIntoView({ block: "center" });
    }
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
  document.addEventListener("unaltraweb:contentchange", enhanceContentSearch);
  document.addEventListener("unaltraweb:documentationprofilechange", rerenderSearchResults);
})();
