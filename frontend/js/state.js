// Shared in-memory state for one browser tab.
export const AVATAR_EMOJI = { fox: "🦊", panda: "🐼", tiger: "🐯", frog: "🐸", owl: "🦉", octopus: "🐙" };

export const S = {
  me: null, // normalized user (guest or registered)
  isGuest: true,
  gate: null, // null | "second_visit"
  csrf: null,
  config: null, // { avatars, cefr_levels, birth_year_min, birth_year_max, ... }
  libTab: "mine",
  libTopic: "",
  libQ: "",
  expTopic: "",
  expQ: "",
};

export function avatarEmoji(key) {
  return AVATAR_EMOJI[key] || "🙂";
}

// Tolerant normalizer: the server may nest settings or use slightly different names.
export function normalizeMe(u) {
  if (!u) return null;
  return {
    ...u,
    nickname: u.nickname || "",
    avatar_key: u.avatar_key || null,
    cefr_level: u.cefr_level || null,
    hide_timer: Boolean(u.hide_timer ?? (u.settings && u.settings.hide_timer) ?? false),
    streak: u.streak ?? 0,
    xp: u.xp ?? 0,
    level: u.level ?? 1,
  };
}
