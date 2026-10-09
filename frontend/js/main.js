import { bootstrap, setGateHandler, startHeartbeat } from "./api.js";
import { configure, start, onGateRequired, renderRoute } from "./router.js";
import { el } from "./ui.js";
import * as home from "./screens/home.js";
import * as gate from "./screens/gate.js";
import * as register from "./screens/register.js";
import * as login from "./screens/login.js";
import * as explore from "./screens/explore.js";
import * as library from "./screens/library.js";
import * as profile from "./screens/profile.js";
import * as practice from "./screens/practice.js";
import * as reflex from "./screens/reflex.js";
import * as auto from "./screens/auto.js";
import * as addphoto from "./screens/addphoto.js";
import * as review from "./screens/review.js";

configure({
  home: { render: home.render, nav: "home" },
  explore: { render: explore.render, nav: "explore" },
  detail: { render: explore.renderDetail, nav: "explore" },
  library: { render: library.render, nav: "library" },
  profile: { render: profile.render, nav: "profile" },
  gate: { render: gate.render, nav: null },
  register: { render: register.render, nav: null },
  login: { render: login.render, nav: null },
  practice: { render: practice.render, nav: null },
  reflex: { render: reflex.render, nav: null },
  auto: { render: auto.render, nav: null },
  addphoto: { render: addphoto.render, nav: null },
  review: { render: review.render, nav: null },
});

setGateHandler(onGateRequired);

async function init() {
  try {
    await bootstrap();
  } catch (e) {
    document
      .getElementById("screen")
      .replaceChildren(el("div", { class: "body" }, el("p", { class: "sub", role: "alert" }, "Không kết nối được máy chủ. Vui lòng tải lại trang.")));
    return;
  }
  start();
  startHeartbeat(renderRoute);
}
init();
