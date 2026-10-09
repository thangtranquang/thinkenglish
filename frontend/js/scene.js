// Photo + markers. Marker coordinates are fractions (0..1) of the original image, so the
// container takes the image's natural aspect ratio once it has loaded.
import { el } from "./ui.js";

export function scene(card, { markers = true, only = null, region = false, onMarker = null, drag = false, labels = true, onMove = null, extra = null } = {}) {
  const img = el("img", { src: card.image_url, alt: "Ảnh " + (card.title || "") });
  const s = el("div", { class: "scene", "data-testid": "scene" }, img);
  if (card.title) s.append(el("span", { class: "cap" }, card.title));
  img.addEventListener("load", () => {
    if (img.naturalWidth && img.naturalHeight) s.style.aspectRatio = img.naturalWidth + " / " + img.naturalHeight;
  });
  img.addEventListener("error", () => img.remove());
  if (markers) {
    (card.labels || []).forEach((lb, i) => {
      if (only !== null && only !== i) return;
      if (lb.x == null || lb.y == null) return;
      const m = el(
        "button",
        {
          type: "button",
          class: "mk" + (drag ? " drag" : "") + (region ? " region" : ""),
          style: `left:${lb.x * 100}%;top:${lb.y * 100}%`,
          "data-testid": "marker",
          "aria-label": drag ? "Kéo để chỉnh vị trí " + lb.word : lb.word,
        },
        el("i"),
        labels && !region ? el("span", { class: "lb" }, lb.word) : null,
      );
      if (onMarker) m.addEventListener("click", () => onMarker(lb, i));
      if (drag) {
        let dragging = false;
        m.addEventListener("pointerdown", (e) => {
          dragging = true;
          try {
            m.setPointerCapture(e.pointerId);
          } catch {
            /* synthetic pointer */
          }
        });
        m.addEventListener("pointermove", (e) => {
          if (!dragging) return;
          const r = s.getBoundingClientRect();
          if (!r.width || !r.height) return;
          lb.x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
          lb.y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
          m.style.left = lb.x * 100 + "%";
          m.style.top = lb.y * 100 + "%";
          if (onMove) onMove(lb, i);
        });
        const end = () => {
          dragging = false;
        };
        m.addEventListener("pointerup", end);
        m.addEventListener("pointercancel", end);
      }
      s.append(m);
    });
  }
  if (extra) s.append(extra);
  return s;
}
