import { S } from "../state.js";
import { openCamera } from "../router.js";
import { el, hdr, screen } from "../ui.js";
import { createCardList, filterControls } from "../cardlist.js";

const TABS = [
  ["mine", "Bài của tôi"],
  ["saved", "Đã lưu"],
  ["due", "Cần ôn lại"],
];

export function render(ctx) {
  const tabs = el("div", { class: "seg", role: "tablist", "aria-label": "Thư viện" });
  const content = el("div", { style: "display:flex;flex-direction:column;gap:12px" });

  function emptyFor(tab) {
    if (tab === "mine" && S.isGuest) {
      return el(
        "div",
        { class: "empty", style: "grid-column:1/3", "data-testid": "library-guest-empty" },
        el("span", { style: "font-size:40px", "aria-hidden": "true" }, "📷"),
        el("p", { class: "sub" }, "Chưa có bài nào. Chụp ảnh đầu tiên của bạn để bắt đầu."),
        el("button", { type: "button", class: "btn", "data-testid": "library-camera", onclick: openCamera }, "📷 Chụp ảnh"),
      );
    }
    const t = tab === "saved" ? "Chưa lưu thẻ nào từ Khám phá." : tab === "due" ? "Chưa có bài nào cần ôn lại." : "Chưa có bài nào.";
    return el("p", { class: "sub center", style: "grid-column:1/3;padding:20px" }, t);
  }

  function drawTabs() {
    tabs.replaceChildren(
      ...TABS.map(([k, t]) =>
        el(
          "button",
          {
            type: "button",
            class: k === S.libTab ? "on" : "",
            role: "tab",
            "aria-selected": k === S.libTab ? "true" : "false",
            "data-testid": "tab-" + k,
            onclick: () => {
              S.libTab = k;
              drawTabs();
              drawContent();
            },
          },
          t,
        ),
      ),
    );
  }

  function drawContent() {
    const tab = S.libTab;
    if (tab === "mine" && S.isGuest) {
      content.replaceChildren(el("div", { class: "grid2" }, emptyFor("mine")));
      return;
    }
    const list = createCardList({
      scope: tab,
      state: S,
      topicKey: "libTopic",
      qKey: "libQ",
      status: true,
      onOpen: (c) => ctx.navigate("practice", { id: c.id }),
      empty: () => emptyFor(tab),
    });
    const { q, chips } = filterControls({ state: S, topicKey: "libTopic", qKey: "libQ", onChange: (typing) => (typing ? list.reloadSoon() : list.reload()) });
    content.replaceChildren(q, chips, list.root);
    list.reload();
  }

  drawTabs();
  drawContent();
  const quick = S.isGuest ? null : el("button", { type: "button", class: "btn sm", "data-testid": "library-quick", onclick: () => ctx.navigate("reflex") }, "⚡ Ôn nhanh");
  return screen(hdr("Thư viện", { right: quick }), el("div", { class: "body" }, tabs, content));
}
