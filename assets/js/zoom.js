// Initialize medium zoom.
$(document).ready(function () {
  const zoomSelector = [
    "[data-zoomable]",
    ".md-figure img:not([data-no-zoom]):not([data-no-figure])",
    ".post-content figure img:not([data-no-zoom]):not([data-no-figure])",
    ".manual-content figure img:not([data-no-zoom]):not([data-no-figure])",
    ".documentation-content figure img:not([data-no-zoom]):not([data-no-figure])",
    ".reading-content figure img:not([data-no-zoom]):not([data-no-figure])",
  ].join(", ");

  medium_zoom = mediumZoom(zoomSelector, {
    background: getComputedStyle(document.documentElement).getPropertyValue("--global-bg-color") + "ee", // + 'ee' for trasparency.
  });
});
