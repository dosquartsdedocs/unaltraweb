(function () {
  var MIN_SCALE = 0.85;
  var MAX_SCALE = 1.25;
  var STEP = 0.1;
  var STORAGE_KEY = "unaltrawebDocumentationFontScale";
  var PROFILE_STORAGE_KEY = "unaltrawebDocumentationProfile";
  var PROFILE_PARAM = "doc_profile";

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
    document.querySelectorAll(".documentation-font-menu").forEach(function (menu) {
      if (menu.dataset.documentationFontMenuReady) return;
      menu.dataset.documentationFontMenuReady = "true";
      menu.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });
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

  function setupSidebarToggle() {
    var layout = document.querySelector(".documentation-layout");
    if (!layout) return;
    var storageKey = "unaltrawebDocumentationTocCollapsed";
    var mobileQuery = window.matchMedia("(max-width: 960px)");
    var stored = localStorage.getItem(storageKey);
    var collapsed = stored === null ? mobileQuery.matches : stored === "true";

    function toggleButtons() {
      return Array.prototype.slice.call(document.querySelectorAll("[data-documentation-sidebar-toggle]"));
    }

    function updateToggleState(isCollapsed) {
      layout.classList.toggle("documentation-toc-collapsed", isCollapsed);
      toggleButtons().forEach(function (button) {
        button.classList.toggle("is-collapsed", isCollapsed);
        button.classList.toggle("collapsed", isCollapsed && button.classList.contains("navbar-toggler"));
        button.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      });
    }

    updateToggleState(collapsed);
    toggleButtons().forEach(function (button) {
      if (button.dataset.documentationToggleReady) return;
      button.dataset.documentationToggleReady = "true";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var nowCollapsed = !layout.classList.contains("documentation-toc-collapsed");
        localStorage.setItem(storageKey, nowCollapsed ? "true" : "false");
        updateToggleState(nowCollapsed);
      });
    });

    if (layout.dataset.documentationOutsideClickReady) return;
    layout.dataset.documentationOutsideClickReady = "true";
    document.addEventListener("click", function (event) {
      if (!mobileQuery.matches || layout.classList.contains("documentation-toc-collapsed")) return;
      var sidebar = layout.querySelector(".documentation-sidebar");
      var clickedToggle = toggleButtons().some(function (button) {
        return button.contains(event.target);
      });
      if ((sidebar && sidebar.contains(event.target)) || clickedToggle) return;
      localStorage.setItem(storageKey, "true");
      updateToggleState(true);
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

  function normalizeProfileToken(value) {
    return (value || "").toString().trim().toLowerCase();
  }

  function profileTokens(value) {
    return (value || "").toString().split(/[\s,]+/).map(normalizeProfileToken).filter(Boolean);
  }

  function readProfileFromUrl() {
    var params = new URLSearchParams(window.location.search);
    return params.has(PROFILE_PARAM) ? normalizeProfileToken(params.get(PROFILE_PARAM)) : null;
  }

  function readStoredProfile() {
    return normalizeProfileToken(localStorage.getItem(PROFILE_STORAGE_KEY));
  }

  function writeStoredProfile(profile) {
    if (profile) {
      localStorage.setItem(PROFILE_STORAGE_KEY, profile);
    } else {
      localStorage.removeItem(PROFILE_STORAGE_KEY);
    }
  }

  function readActiveProfile() {
    var urlProfile = readProfileFromUrl();
    if (urlProfile !== null) {
      writeStoredProfile(urlProfile);
      return urlProfile;
    }
    return readStoredProfile();
  }

  function updateProfileUrl(profile) {
    if (!window.history || !window.history.replaceState) return;
    var params = new URLSearchParams(window.location.search);
    if (profile) params.set(PROFILE_PARAM, profile);
    if (!profile) params.delete(PROFILE_PARAM);
    var query = params.toString();
    var nextUrl = window.location.pathname + (query ? "?" + query : "") + window.location.hash;
    window.history.replaceState({}, "", nextUrl);
  }

  function syncProfileControls(container, activeProfile) {
    if (!container) return;
    container.classList.toggle("has-active-profile", Boolean(activeProfile));
    container.querySelectorAll("[data-documentation-profile-select]").forEach(function (select) {
      select.value = activeProfile;
    });
  }

  function profileExists(container, profile) {
    if (!container || !profile) return false;
    return Array.prototype.slice.call(container.querySelectorAll("[data-documentation-profile-select] option")).some(function (option) {
      return normalizeProfileToken(option.value) === profile;
    });
  }

  function validActiveProfile(container) {
    var profile = readActiveProfile();
    if (!profile) return "";
    if (profileExists(container, profile)) return profile;
    writeStoredProfile("");
    updateProfileUrl("");
    return "";
  }

  function itemMatchesProfile(item, activeProfile) {
    if (!activeProfile) return true;
    var profiles = profileTokens(item && item.dataset ? item.dataset.documentationProfiles : "");
    return profiles.length === 0 || profiles.indexOf(activeProfile) !== -1;
  }

  function visibleElements(nodes) {
    return Array.prototype.slice.call(nodes).filter(function (node) { return !node.hidden; });
  }

  function syncDocumentationTreeLine(tree) {
    if (!tree) return;
    var sections = Array.prototype.slice.call(tree.querySelectorAll("[data-documentation-tree-id]"));
    sections.forEach(function (section) {
      delete section.dataset.documentationVisibleSection;
      delete section.dataset.documentationFirstVisibleSection;
      delete section.dataset.documentationLastVisibleSection;
    });

    var visibleSections = visibleElements(sections);
    tree.hidden = tree.dataset.documentationProfileEmpty === "true";
    var hasVisibleBranch = visibleSections.some(function (section) {
      return section.open && visibleElements(section.querySelectorAll("[data-documentation-profile-item]")).length > 0;
    });
    tree.classList.toggle("has-visible-documentation-sections", visibleSections.length > 0);
    tree.classList.toggle("has-multiple-visible-documentation-sections", visibleSections.length > 1);
    tree.classList.toggle("has-visible-documentation-branches", hasVisibleBranch);

    if (!visibleSections.length) return;
    visibleSections.forEach(function (section) { section.dataset.documentationVisibleSection = "true"; });
    visibleSections[0].dataset.documentationFirstVisibleSection = "true";
    visibleSections[visibleSections.length - 1].dataset.documentationLastVisibleSection = "true";

    if (visibleSections.length < 2 && !hasVisibleBranch) return;
    var treeRect = tree.getBoundingClientRect();
    var firstSection = visibleSections[0];
    var lastSection = visibleSections[visibleSections.length - 1];
    var firstMark = firstSection.querySelector(".documentation-accordion-mark") || firstSection.querySelector("summary") || firstSection;
    var lastMark = lastSection.querySelector(".documentation-accordion-mark") || lastSection.querySelector("summary") || lastSection;
    if (lastSection.open) {
      var lastSectionItems = visibleElements(lastSection.querySelectorAll("[data-documentation-profile-item]"));
      if (lastSectionItems.length) lastMark = lastSectionItems[lastSectionItems.length - 1];
    }
    var firstRect = firstMark.getBoundingClientRect();
    var lastRect = lastMark.getBoundingClientRect();
    var firstCenter = firstRect.top + firstRect.height / 2 - treeRect.top;
    var lastCenter = lastRect.top + lastRect.height / 2 - treeRect.top;
    tree.style.setProperty("--documentation-tree-line-top", firstCenter.toFixed(2) + "px");
    tree.style.setProperty("--documentation-tree-line-bottom", Math.max(0, treeRect.height - lastCenter).toFixed(2) + "px");
  }

  function syncDocumentationTrees() {
    document.querySelectorAll("[data-documentation-tree]").forEach(syncDocumentationTreeLine);
  }

  function scheduleDocumentationTreeSync() {
    window.requestAnimationFrame(syncDocumentationTrees);
  }

  function setupDocumentationTreeLineSync() {
    if (document.documentElement.dataset.documentationTreeLineSyncReady) return;
    document.documentElement.dataset.documentationTreeLineSyncReady = "true";
    window.addEventListener("resize", scheduleDocumentationTreeSync, { passive: true });
  }

  function updateProfileSections(activeProfile) {
    document.querySelectorAll("[data-documentation-tree-id]").forEach(function (section) {
      var items = Array.prototype.slice.call(section.querySelectorAll("[data-documentation-profile-item]"));
      var hasVisibleItem = items.some(function (item) { return !item.hidden; });
      section.hidden = Boolean(activeProfile) && items.length > 0 && !hasVisibleItem;
    });
    document.querySelectorAll("[data-documentation-tree]").forEach(function (tree) {
      var sections = Array.prototype.slice.call(tree.querySelectorAll("[data-documentation-tree-id]"));
      var hasVisibleSection = sections.some(function (section) { return !section.hidden; });
      tree.dataset.documentationProfileEmpty = Boolean(activeProfile) && sections.length > 0 && !hasVisibleSection ? "true" : "false";
    });
    document.querySelectorAll(".documentation-index-section").forEach(function (section) {
      var cards = Array.prototype.slice.call(section.querySelectorAll(".documentation-card[data-documentation-profile-item]"));
      var hasVisibleCard = cards.some(function (card) { return !card.hidden; });
      section.hidden = Boolean(activeProfile) && cards.length > 0 && !hasVisibleCard;
    });
    document.querySelectorAll(".documentation-index").forEach(function (index) {
      var sections = Array.prototype.slice.call(index.querySelectorAll(".documentation-index-section"));
      var hasVisibleSection = sections.some(function (section) { return !section.hidden; });
      index.hidden = Boolean(activeProfile) && sections.length > 0 && !hasVisibleSection;
    });
    scheduleDocumentationTreeSync();
  }

  function updateCurrentPageProfileNotice(activeProfile) {
    var currentPage = document.querySelector("[data-documentation-current-page]");
    var notice = document.querySelector("[data-documentation-profile-notice]");
    if (!currentPage || !notice) return;
    notice.hidden = !activeProfile || itemMatchesProfile(currentPage, activeProfile);
  }

  function applyDocumentationProfile(activeProfile) {
    document.body.classList.toggle("documentation-profile-active", Boolean(activeProfile));
    document.querySelectorAll("[data-documentation-profile-item]").forEach(function (item) {
      var visible = itemMatchesProfile(item, activeProfile);
      item.hidden = !visible;
      item.classList.toggle("documentation-profile-hidden", !visible);
    });
    updateProfileSections(activeProfile);
    updateCurrentPageProfileNotice(activeProfile);
  }

  function emitProfileChange(activeProfile) {
    document.dispatchEvent(new CustomEvent("unaltraweb:documentationprofilechange", { detail: { profile: activeProfile } }));
  }

  function setupDocumentationProfiles() {
    var container = document.querySelector("[data-documentation-profile-switcher]");
    if (!container) {
      applyDocumentationProfile("");
      return;
    }
    var activeProfile = validActiveProfile(container);
    syncProfileControls(container, activeProfile);
    applyDocumentationProfile(activeProfile);

    if (container.dataset.documentationProfilesReady) return;
    container.dataset.documentationProfilesReady = "true";
    container.addEventListener("change", function (event) {
      var select = event.target.closest("[data-documentation-profile-select]");
      if (!select) return;
      activeProfile = normalizeProfileToken(select.value);
      writeStoredProfile(activeProfile);
      updateProfileUrl(activeProfile);
      syncProfileControls(container, activeProfile);
      applyDocumentationProfile(activeProfile);
      emitProfileChange(activeProfile);
    });
  }

  function setupDocumentationTree() {
    document.querySelectorAll("[data-documentation-tree]").forEach(function (tree) {
      if (tree.dataset.documentationTreeReady) return;
      tree.dataset.documentationTreeReady = "true";
      var docsPath = window.location.pathname;
      var docsLink = tree.querySelector("a[href*='/docs/']");
      if (docsLink) {
        try {
          docsPath = new URL(docsLink.href, window.location.href).pathname;
        } catch (error) {
          docsPath = window.location.pathname;
        }
      }
      var docsIndex = docsPath.indexOf("/docs/");
      var docsRoot = docsIndex === -1 ? docsPath.split("/").slice(0, -1).join("/") : docsPath.slice(0, docsIndex + "/docs".length);
      var storageKey = "unaltrawebDocumentationTree:" + docsRoot;
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
        } else if (hasActive) {
          details.open = true;
        }
        if (hasActive) details.dataset.documentationActiveSection = "true";
        details.addEventListener("toggle", function () {
          stored[id] = details.open;
          localStorage.setItem(storageKey, JSON.stringify(stored));
          scheduleDocumentationTreeSync();
        });
      });
      scheduleDocumentationTreeSync();
    });
  }

  function setupPageToc() {
    var container = document.querySelector("[data-documentation-page-toc-container]");
    var list = document.querySelector("[data-documentation-page-toc]");
    var content = document.querySelector(".documentation-content");
    if (!container || !list || !content) return;

    var headings = Array.prototype.slice.call(content.querySelectorAll("h2[id], h3[id]"));
    if (!headings.length) {
      container.hidden = true;
      list.innerHTML = "";
      return;
    }

    list.innerHTML = "";
    headings.forEach(function (heading) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      var level = heading.tagName && heading.tagName.toLowerCase() === "h3" ? "level-3" : "level-2";

      item.className = "documentation-section-toc-item";
      link.className = "documentation-nav-link documentation-section-toc-link " + level;
      link.href = "#" + heading.id;
      link.textContent = heading.textContent || heading.id;
      item.appendChild(link);
      list.appendChild(item);
    });
    container.hidden = false;

    var links = Array.prototype.slice.call(list.querySelectorAll("a[href^='#']"));

    function updateActivePageTocLink() {
      var activeIndex = 0;
      headings.forEach(function (heading, index) {
        if (heading.getBoundingClientRect().top <= 120) activeIndex = index;
      });
      links.forEach(function (link, index) {
        var active = index === activeIndex;
        link.classList.toggle("active", active);
        if (active) {
          link.setAttribute("aria-current", "location");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }

    if (!container.dataset.documentationPageTocScrollReady) {
      container.dataset.documentationPageTocScrollReady = "true";
      var ticking = false;
      window.addEventListener(
        "scroll",
        function () {
          if (ticking) return;
          ticking = true;
          window.requestAnimationFrame(function () {
            updateActivePageTocLink();
            ticking = false;
          });
        },
        { passive: true }
      );
      window.addEventListener("hashchange", updateActivePageTocLink);
    }
    updateActivePageTocLink();
  }

  function enhanceDocumentation() {
    setupSidebarToggle();
    setupFontControls();
    updateThemeLabels();
    setupDocumentationProfiles();
    setupDocumentationTreeLineSync();
    setupDocumentationTree();
    setupPageToc();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceDocumentation);
  } else {
    enhanceDocumentation();
  }
  document.addEventListener("unaltraweb:contentchange", enhanceDocumentation);
  document.addEventListener("unaltraweb:themechange", updateThemeLabels);
})();
