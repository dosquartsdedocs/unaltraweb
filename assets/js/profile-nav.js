(function () {
  function currentProfileUsesDrawer() {
    return document.body.classList.contains("site-profile-unaltreprojecte") || document.body.classList.contains("site-profile-unaltreselfie");
  }

  function setupProfileNavbar() {
    if (!currentProfileUsesDrawer()) return;
    var navbar = document.getElementById("navbar");
    if (!navbar || navbar.dataset.profileNavbarReady) return;
    var container = navbar.querySelector(".container");
    var collapse = navbar.querySelector("#navbarNav");
    var toggler = navbar.querySelector(".navbar-toggler[data-target='#navbarNav']");
    var utilities = navbar.querySelector(".profile-navbar-utilities");
    var brand = navbar.querySelector(".navbar-brand");
    var navList = collapse ? collapse.querySelector(".navbar-nav") : null;
    if (!container || !collapse || !toggler || !utilities || !brand || !navList) return;
    navbar.dataset.profileNavbarReady = "true";

    function measureNavWidth() {
      var previousCollapseStyle = collapse.getAttribute("style");
      var previousNavStyle = navList.getAttribute("style");
      collapse.style.display = "block";
      collapse.style.position = "absolute";
      collapse.style.visibility = "hidden";
      collapse.style.width = "max-content";
      collapse.style.height = "auto";
      collapse.style.pointerEvents = "none";
      navList.style.flexDirection = "row";
      navList.style.flexWrap = "nowrap";
      var width = navList.scrollWidth;
      if (previousCollapseStyle === null) collapse.removeAttribute("style");
      else collapse.setAttribute("style", previousCollapseStyle);
      if (previousNavStyle === null) navList.removeAttribute("style");
      else navList.setAttribute("style", previousNavStyle);
      return width;
    }

    function updateOpenState() {
      document.body.classList.toggle("profile-navbar-drawer-open", navbar.classList.contains("profile-navbar-drawer") && collapse.classList.contains("show"));
    }

    function updateMode() {
      navbar.classList.remove("profile-navbar-drawer");
      var containerWidth = container.getBoundingClientRect().width;
      var totalWidth = brand.getBoundingClientRect().width + utilities.getBoundingClientRect().width + measureNavWidth() + 72;
      navbar.classList.toggle("profile-navbar-drawer", totalWidth > containerWidth || window.innerWidth < 576);
      updateOpenState();
    }

    function hideDrawer() {
      if (window.jQuery && window.jQuery.fn && window.jQuery.fn.collapse) {
        window.jQuery(collapse).collapse("hide");
      } else {
        collapse.classList.remove("show");
        toggler.classList.add("collapsed");
        toggler.setAttribute("aria-expanded", "false");
        updateOpenState();
      }
    }

    var resizeTimer = null;
    function scheduleUpdateMode() {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(updateMode, 80);
    }

    document.addEventListener("click", function (event) {
      if (!document.body.classList.contains("profile-navbar-drawer-open")) return;
      if (collapse.contains(event.target) || toggler.contains(event.target) || utilities.contains(event.target)) return;
      hideDrawer();
    });

    collapse.addEventListener("click", function (event) {
      if (!navbar.classList.contains("profile-navbar-drawer")) return;
      var link = event.target.closest("a.nav-link, a.dropdown-item");
      if (!link || link.classList.contains("dropdown-toggle")) return;
      hideDrawer();
    });

    new MutationObserver(updateOpenState).observe(collapse, { attributes: true, attributeFilter: ["class"] });
    window.addEventListener("resize", scheduleUpdateMode);
    updateMode();
    window.setTimeout(updateMode, 180);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupProfileNavbar);
  } else {
    setupProfileNavbar();
  }
  document.addEventListener("unaltraweb:contentchange", setupProfileNavbar);
})();
