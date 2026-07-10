"use strict";
// A shared SVG layer positioned over an element (the original image, or the
// sim stage). Content is drawn from FRACTIONAL coordinates so it survives
// re-renders and window resizes; call sync() after layout changes.
// Used by the freeform-shape editor (and the pattern sizing widget later).
window.CapOverlay = {
  attach(hostEl, alignEl) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "capoverlay");
    Object.assign(svg.style, {
      position: "absolute", left: "0", top: "0",
      pointerEvents: "none", overflow: "visible",
    });
    hostEl.appendChild(svg);
    const target = () => alignEl || hostEl;

    function sync() {
      const host = hostEl.getBoundingClientRect();
      const box = target().getBoundingClientRect();
      Object.assign(svg.style, {
        left: (box.left - host.left) + "px",
        top: (box.top - host.top) + "px",
        width: box.width + "px",
        height: box.height + "px",
      });
    }

    return {
      svg,
      sync,
      rect: () => target().getBoundingClientRect(),
      toFrac(clientX, clientY) {
        const r = target().getBoundingClientRect();
        return { x: (clientX - r.left) / r.width, y: (clientY - r.top) / r.height };
      },
      fromFrac(fx, fy) {
        const r = target().getBoundingClientRect();
        return { x: fx * r.width, y: fy * r.height };
      },
      clear() { while (svg.firstChild) svg.removeChild(svg.firstChild); },
      el(name, attrs) {
        const e = document.createElementNS("http://www.w3.org/2000/svg", name);
        for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
        svg.appendChild(e);
        return e;
      },
    };
  },
};
