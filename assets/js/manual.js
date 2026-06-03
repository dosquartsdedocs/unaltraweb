(function () {
  var MIN_SCALE = 0.85;
  var MAX_SCALE = 1.25;
  var STEP = 0.1;
  var pageTocCleanup = null;

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
    document.querySelectorAll(".manual-font-menu").forEach(function (menu) {
      if (menu.dataset.manualFontMenuReady) return;
      menu.dataset.manualFontMenuReady = "true";
      menu.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });
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
    if (root.getAttribute("data-manual-numbered") === "false") return;

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
    setupPageTocActiveState(target, headings);
  }

  function setupPageTocActiveState(target, headings) {
    if (pageTocCleanup) {
      pageTocCleanup();
      pageTocCleanup = null;
    }

    var links = Array.prototype.slice.call(target.querySelectorAll("a[href^='#']"));
    if (!headings.length || !links.length) return;

    var linkById = {};
    links.forEach(function (link) {
      var id = decodeURIComponent(link.getAttribute("href").slice(1));
      linkById[id] = link;
    });

    function activate(id) {
      links.forEach(function (link) {
        link.classList.remove("active");
        link.removeAttribute("aria-current");
      });
      var activeLink = linkById[id];
      if (!activeLink) return;
      activeLink.classList.add("active");
      activeLink.setAttribute("aria-current", "location");
      var parentSection = activeLink.closest("details");
      if (parentSection) parentSection.open = true;
    }

    function currentHeadingId() {
      var offset = Math.min(window.innerHeight * 0.28, 180);
      var current = headings[0];
      headings.forEach(function (heading) {
        if (heading.getBoundingClientRect().top <= offset) current = heading;
      });
      return current.id;
    }

    var ticking = false;
    function updateActive() {
      ticking = false;
      activate(currentHeadingId());
    }
    function scheduleUpdate() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateActive);
    }

    updateActive();
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    pageTocCleanup = function () {
      window.removeEventListener("scroll", scheduleUpdate);
      window.removeEventListener("resize", scheduleUpdate);
    };
  }

  function setupSidebarToggle() {
    var layout = document.querySelector(".manual-layout");
    if (!layout) return;
    var storageKey = "unaltrawebManualSidebarCollapsed";
    var mobileQuery = window.matchMedia("(max-width: 960px)");
    var stored = localStorage.getItem(storageKey);
    var collapsed = stored === null ? mobileQuery.matches : stored === "true";

    function toggleButtons() {
      return Array.prototype.slice.call(document.querySelectorAll("[data-manual-sidebar-toggle]"));
    }

    function updateToggleState(isCollapsed) {
      layout.classList.toggle("manual-sidebar-collapsed", isCollapsed);
      toggleButtons().forEach(function (button) {
        button.classList.toggle("is-collapsed", isCollapsed);
        button.classList.toggle("collapsed", isCollapsed && button.classList.contains("navbar-toggler"));
        button.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      });
    }

    updateToggleState(collapsed);
    toggleButtons().forEach(function (button) {
      if (button.dataset.manualToggleReady) return;
      button.dataset.manualToggleReady = "true";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var nowCollapsed = !layout.classList.contains("manual-sidebar-collapsed");
        localStorage.setItem(storageKey, nowCollapsed ? "true" : "false");
        updateToggleState(nowCollapsed);
      });
    });

    if (layout.dataset.manualOutsideClickReady) return;
    layout.dataset.manualOutsideClickReady = "true";
    document.addEventListener("click", function (event) {
      if (!mobileQuery.matches || layout.classList.contains("manual-sidebar-collapsed")) return;
      var panel = layout.querySelector(".manual-toc-panel") || layout.querySelector(".manual-sidebar");
      var clickedToggle = toggleButtons().some(function (button) {
        return button.contains(event.target);
      });
      if ((panel && panel.contains(event.target)) || clickedToggle) return;
      localStorage.setItem(storageKey, "true");
      updateToggleState(true);
    });
  }

  function enhanceManual() {
    setupSidebarToggle();
    setupFontControls();
    addNumbering();
    buildPageToc();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceManual);
  } else {
    enhanceManual();
  }
  document.addEventListener("unaltraweb:contentchange", enhanceManual);
})();
