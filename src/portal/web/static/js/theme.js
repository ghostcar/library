/* Theme toggle (CSP-safe: external file, no inline script).
   Default theme: Astral (dark). Persisted in localStorage. */
(function () {
  "use strict";
  var stored = null;
  try {
    stored = localStorage.getItem("library-theme");
  } catch (e) {
    /* storage unavailable — keep default */
  }
  if (stored === "solar" || stored === "astral") {
    document.documentElement.setAttribute("data-theme", stored);
  }

  function toggle() {
    var current =
      document.documentElement.getAttribute("data-theme") || "astral";
    var next = current === "astral" ? "solar" : "astral";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("library-theme", next);
    } catch (e) {
      /* ignore */
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", toggle);
    }
  });
})();
