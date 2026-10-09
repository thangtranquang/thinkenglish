// Stub: filled in by slice 8.
import { el, hdr, screen } from "../ui.js";

export function render(ctx) {
  return screen(
    hdr("review", { onBack: () => ctx.navigate("home") }),
    el("div", { class: "body", "data-testid": "screen-review" }, el("p", { class: "sub" }, "Màn hình này sẽ sớm có mặt.")),
  );
}
