window.MathJax = {
  loader: {
    load: ["[tex]/cancel"],
  },
  tex: {
    tags: window.unaltrawebMathJaxTags || "all",
    packages: { "[+]": ["cancel"] },
    inlineMath: [
      ["$", "$"],
      ["\\(", "\\)"],
    ],
    displayMath: [
      ["$$", "$$"],
      ["\\[", "\\]"],
    ],
    processEscapes: true,
    processEnvironments: true,
    macros: {
      cm: "\\,\\mathrm{cm}",
      mm: "\\,\\mathrm{mm}",
      m: "\\,\\mathrm{m}",
      km: "\\,\\mathrm{km}",
      cms: "\\,\\mathrm{cm^2}",
      squarekilometre: "\\,\\mathrm{km^2}",
      hectare: "\\,\\mathrm{ha}",
      ha: "\\,\\mathrm{ha}",
    },
  },
  options: {
    renderActions: {
      addCss: [
        200,
        function (doc) {
          const style = document.createElement("style");
          style.innerHTML = `
          .mjx-container {
            color: inherit;
          }
        `;
          document.head.appendChild(style);
        },
        "",
      ],
    },
  },
};
