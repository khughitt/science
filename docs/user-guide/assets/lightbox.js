/* Click-to-zoom for inline figure SVGs.
 *
 * The figures are inline `<svg class="sci-figure">` in the light DOM, so a
 * standard image lightbox (which targets `<img>`) does not see them. This
 * clones the clicked figure into a full-screen overlay appended to <body>.
 * Because the clone keeps its classes and lives in the same document, it
 * inherits palette.css and the active color scheme, so it stays legible and
 * theme-correct at full size. No external dependencies.
 */
(function () {
  "use strict";

  function openLightbox(svg) {
    var overlay = document.createElement("div");
    overlay.className = "sci-lightbox";

    var card = document.createElement("div");
    card.className = "sci-lightbox-card";

    var clone = svg.cloneNode(true);
    clone.classList.remove("sci-zoomable");
    clone.removeAttribute("tabindex");
    clone.removeAttribute("role");
    clone.style.cursor = "";
    card.appendChild(clone);

    // Carry the figure's caption into the modal, below the figure. Deep-clone
    // the node (preserving inline <code> etc.) rather than copying innerHTML.
    var figure = svg.closest("figure");
    var caption = figure ? figure.querySelector("figcaption") : null;
    if (caption) {
      var captionClone = caption.cloneNode(true);
      captionClone.className = "sci-lightbox-caption";
      card.appendChild(captionClone);
    }

    overlay.appendChild(card);
    document.body.appendChild(overlay);

    function close() {
      document.removeEventListener("keydown", onKey);
      overlay.classList.remove("is-open");
      window.setTimeout(function () {
        if (overlay.parentNode) {
          overlay.parentNode.removeChild(overlay);
        }
      }, 200);
    }

    function onKey(event) {
      if (event.key === "Escape") {
        close();
      }
    }

    overlay.addEventListener("click", close);
    document.addEventListener("keydown", onKey);

    // Next frame so the opacity transition runs.
    window.requestAnimationFrame(function () {
      overlay.classList.add("is-open");
    });
  }

  function wire(svg) {
    if (svg.dataset.lightbox) {
      return;
    }
    svg.dataset.lightbox = "1";
    svg.classList.add("sci-zoomable");
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("role", "button");

    svg.addEventListener("click", function () {
      openLightbox(svg);
    });
    svg.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openLightbox(svg);
      }
    });
  }

  function init() {
    var figures = document.querySelectorAll("svg.sci-figure");
    for (var i = 0; i < figures.length; i++) {
      wire(figures[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
