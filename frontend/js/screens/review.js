// Review: check the AI labels (drag, rename, delete), choose a title and privacy, then save the card.
import { get, post } from "../api.js";
import { scene } from "../scene.js";
import { el, errorMessage, hdr, screen, toast } from "../ui.js";

const MAX_LABELS = 8;

export async function render(ctx) {
  const back = () => ctx.navigate("addphoto");
  let up;
  try {
    up = await get("/api/uploads/" + encodeURIComponent(ctx.id));
  } catch (e) {
    return screen(hdr("Xem lại kết quả AI", { onBack: back }), el("div", { class: "body", "data-testid": "screen-review" }, el("p", { class: "sub center", role: "alert" }, e.status === 404 ? "Không tìm thấy ảnh này." : errorMessage(e))));
  }
  if (up.status !== "ready") {
    return screen(
      hdr("Xem lại kết quả AI", { onBack: back }),
      el("div", { class: "body", "data-testid": "screen-review" }, el("p", { class: "sub center", role: "alert" }, "Ảnh chưa xử lý xong. Vui lòng quay lại và thử lại."), el("button", { type: "button", class: "btn", onclick: back }, "Quay lại")),
    );
  }

  const labels = up.labels.map((l) => ({ id: l.id, word: l.word, x: l.x ?? 0.5, y: l.y ?? 0.5 }));
  const draft = { title: up.topic || "Ảnh của tôi", image_url: up.image_url || `/api/uploads/${encodeURIComponent(up.content_id)}/image`, labels };
  let visibility = "private";
  let saving = false;

  const sc = el("div");
  const list = el("div", { style: "display:grid;gap:8px", "data-testid": "review-labels" });
  const err = el("p", { class: "err", role: "alert", "aria-live": "assertive", "data-testid": "review-error" });
  const title = el("input", { type: "text", id: "ttl", maxlength: "60", value: draft.title, "data-testid": "review-title" });
  const saveBtn = el("button", { type: "button", class: "btn", "data-testid": "review-save", onclick: save }, "Lưu");
  const body = el("div", { class: "body", "data-testid": "screen-review" });

  const drawScene = () => sc.replaceChildren(scene(draft, { drag: true }));
  const drawList = () =>
    list.replaceChildren(
      ...labels.map((lb, i) => {
        const inp = el("input", { type: "text", maxlength: "40", value: lb.word, "aria-label": "Tên nhãn " + (i + 1), "data-testid": "review-label-input" });
        inp.addEventListener("input", () => {
          lb.word = inp.value;
          const tag = sc.querySelectorAll(".lb")[i];
          if (tag) tag.textContent = inp.value;
        });
        return el(
          "div",
          { class: "row" },
          inp,
          el("button", { type: "button", class: "ib", "aria-label": "Xóa nhãn " + lb.word, "data-testid": "review-label-delete", onclick: () => { labels.splice(i, 1); drawScene(); drawList(); } }, "🗑"),
        );
      }),
    );
  drawScene();
  drawList();

  async function save() {
    if (saving) return;
    err.textContent = "";
    if (!labels.length) return void (err.textContent = "Cần ít nhất 1 nhãn.");
    if (labels.length > MAX_LABELS) return void (err.textContent = "Tối đa 8 nhãn, hãy xóa bớt.");
    if (labels.some((l) => !l.word.trim())) return void (err.textContent = "Nhãn không được để trống.");
    saving = true;
    saveBtn.disabled = true;
    let card;
    try {
      card = await post("/api/cards", {
        content_id: up.content_id,
        title: title.value.trim() || "Ảnh của tôi",
        label_overrides: labels.map((l) => ({ id: l.id, word: l.word.trim(), x: l.x, y: l.y })),
      });
    } catch (e) {
      saving = false;
      saveBtn.disabled = false;
      err.textContent = e.error === "not_ready" ? "Ảnh chưa xử lý xong." : e.status === 403 ? "" : errorMessage(e);
      return;
    }
    let shareNote = null;
    if (visibility === "public") shareNote = await share(card.id);
    done(card, shareNote);
  }

  // Returns a Vietnamese note when the card could not be shared (it stays private), null on success.
  async function share(cardId) {
    try {
      await post(`/api/cards/${encodeURIComponent(cardId)}/share`);
      return null;
    } catch (e) {
      if (e.status === 422) return (e.fields && e.fields.message) || "Ảnh này không thể chia sẻ công khai nên vẫn ở chế độ riêng tư.";
      return errorMessage(e);
    }
  }

  function done(card, shareNote) {
    toast("Đã lưu thẻ");
    body.replaceChildren(
      el(
        "div",
        { class: "card", "data-testid": "review-saved" },
        el("h2", {}, "Đã lưu: " + card.title),
        el("p", { class: "sub" }, shareNote ? "Thẻ đang ở chế độ riêng tư." : visibility === "public" ? "Thẻ đã được chia sẻ công khai." : "Thẻ ở chế độ riêng tư: chỉ mình bạn thấy."),
        shareNote ? el("p", { class: "err", role: "alert", "data-testid": "review-share-error" }, shareNote) : null,
      ),
      el("button", { type: "button", class: "btn", "data-testid": "review-practice", onclick: () => ctx.navigate("practice", { id: card.id }) }, "Luyện tập ngay"),
      visibility !== "public" && !shareNote
        ? el(
            "button",
            {
              type: "button",
              class: "btn sec",
              "data-testid": "review-share",
              onclick: async (e) => {
                e.currentTarget.disabled = true;
                const note = await share(card.id);
                if (note) body.append(el("p", { class: "err", role: "alert", "data-testid": "review-share-error" }, note));
                else toast("Đã chia sẻ công khai");
              },
            },
            "Chia sẻ công khai",
          )
        : null,
      el("button", { type: "button", class: "btn sec", onclick: () => ctx.navigate("library") }, "Về Thư viện"),
    );
  }

  const radios = [
    ["private", "Riêng tư (mặc định)", "Chỉ mình bạn thấy."],
    ["public", "Công khai", "Chỉ khi ảnh đạt kiểm tra an toàn (không có mặt người, thông tin cá nhân)."],
  ].map(([k, t, d]) => {
    const i = el("input", { type: "radio", name: "vis", value: k, checked: k === visibility, "data-testid": "review-vis-" + k });
    i.addEventListener("change", () => (visibility = k));
    return el("label", { class: "opt" }, i, el("div", {}, el("b", {}, t), el("span", {}, d)));
  });

  body.append(
    el("p", { class: "sub" }, "AI có thể sai. Kéo chấm cam đến đúng vật, sửa hoặc xóa nhãn chưa đúng trước khi lưu."),
    sc,
    el("h3", {}, "Nhãn (1–8)"),
    list,
    el("label", { class: "f", for: "ttl" }, "Tiêu đề", title),
    el("h3", {}, "Ai được xem?"),
    el("div", { style: "display:grid;gap:8px", role: "radiogroup", "aria-label": "Ai được xem" }, ...radios),
    saveBtn,
    err,
  );
  return screen(hdr("Xem lại kết quả AI", { onBack: back }), body);
}
