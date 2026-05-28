(function () {
  var STORAGE_KEY = "unaltrawebDeveloperSwitcherPosition";

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function viewportPosition(element, left, top) {
    var margin = 8;
    var width = element.offsetWidth;
    var height = element.offsetHeight;
    return {
      left: clamp(left, margin, Math.max(margin, window.innerWidth - width - margin)),
      top: clamp(top, margin, Math.max(margin, window.innerHeight - height - margin)),
    };
  }

  function applyPosition(element, position) {
    var next = viewportPosition(element, position.left, position.top);
    element.style.left = next.left + "px";
    element.style.top = next.top + "px";
    element.style.right = "auto";
    element.style.bottom = "auto";
  }

  function setupDeveloperSwitcher() {
    var switcher = document.querySelector("[data-developer-mode-switcher]");
    if (!switcher || switcher.dataset.developerModeReady) return;
    switcher.dataset.developerModeReady = "true";

    var handle = switcher.querySelector("[data-developer-mode-handle]") || switcher;
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch (error) {
      saved = null;
    }
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
      applyPosition(switcher, saved);
    }

    switcher.querySelectorAll("[data-developer-profile-link]").forEach(function (link) {
      link.setAttribute("target", "_self");
      link.addEventListener("click", function (event) {
        event.preventDefault();
        window.location.assign(link.href);
      });
    });

    handle.addEventListener("dblclick", function () {
      localStorage.removeItem(STORAGE_KEY);
      switcher.style.left = "";
      switcher.style.top = "";
      switcher.style.right = "";
      switcher.style.bottom = "";
    });

    handle.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) return;
      event.preventDefault();
      var rect = switcher.getBoundingClientRect();
      var offsetX = event.clientX - rect.left;
      var offsetY = event.clientY - rect.top;
      switcher.classList.add("is-dragging");
      handle.setPointerCapture(event.pointerId);

      function move(moveEvent) {
        applyPosition(switcher, {
          left: moveEvent.clientX - offsetX,
          top: moveEvent.clientY - offsetY,
        });
      }

      function finish(upEvent) {
        switcher.classList.remove("is-dragging");
        handle.releasePointerCapture(upEvent.pointerId);
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", finish);
        document.removeEventListener("pointercancel", finish);
        var finalRect = switcher.getBoundingClientRect();
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ left: finalRect.left, top: finalRect.top }));
      }

      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", finish);
      document.addEventListener("pointercancel", finish);
    });

    window.addEventListener("resize", function () {
      if (!switcher.style.left || !switcher.style.top) return;
      applyPosition(switcher, {
        left: switcher.getBoundingClientRect().left,
        top: switcher.getBoundingClientRect().top,
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupDeveloperSwitcher);
  } else {
    setupDeveloperSwitcher();
  }
})();
