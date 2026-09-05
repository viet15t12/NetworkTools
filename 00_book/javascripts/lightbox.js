/**
 * CAMS Lightbox – Vanilla JS, no dependencies.
 * Click any content image → full-screen overlay with animation.
 * Close: click overlay | press Escape | click × button.
 */
(function () {
  "use strict";

  /* ── Build overlay DOM ─────────────────────────────────── */
  function buildOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "cams-lightbox-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Xem ảnh phóng to");

    const img = document.createElement("img");
    img.alt = "";

    const caption = document.createElement("div");
    caption.className = "cams-lightbox-caption";

    const closeBtn = document.createElement("button");
    closeBtn.className = "cams-lightbox-close";
    closeBtn.innerHTML = "&#x2715;";
    closeBtn.setAttribute("aria-label", "Đóng");

    overlay.appendChild(closeBtn);
    overlay.appendChild(img);
    overlay.appendChild(caption);
    document.body.appendChild(overlay);

    return { overlay, img, caption, closeBtn };
  }

  /* ── Open / Close helpers ───────────────────────────────── */
  let els = null;
  let lastFocused = null;

  function open(src, alt) {
    if (!els) els = buildOverlay();
    lastFocused = document.activeElement;

    els.img.src = src;
    els.img.alt = alt || "";
    els.caption.textContent = alt || "";
    els.caption.style.display = alt ? "block" : "none";

    // Force reflow so transition plays
    els.overlay.offsetHeight; // eslint-disable-line no-unused-expressions
    els.overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
    els.closeBtn.focus();
  }

  function close() {
    if (!els) return;
    els.overlay.classList.remove("is-open");
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
  }

  /* ── Event wiring ───────────────────────────────────────── */
  function attachListeners() {
    if (!els) els = buildOverlay();

    // Close on overlay background click (not on the image itself)
    els.overlay.addEventListener("click", function (e) {
      if (e.target === els.overlay || e.target === els.img) close();
    });

    // Close button
    els.closeBtn.addEventListener("click", close);

    // Keyboard: Escape to close
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  }

  /* ── Init: delegate click from content area ─────────────── */
  function init() {
    attachListeners();

    // Use event delegation on the main content wrapper
    document.addEventListener("click", function (e) {
      const target = e.target;

      // Only images inside .md-typeset (content area), not nav/header logos
      if (
        target.tagName === "IMG" &&
        target.closest(".md-typeset") &&
        !target.closest("a") // skip images that are already links
      ) {
        e.preventDefault();
        open(target.src, target.alt);
      }
    });
  }

  /* ── Bootstrap after MkDocs Material instant navigation ─── */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-init on MkDocs Material instant navigation page change
  document.addEventListener("DOMContentSwitch", init);
})();
