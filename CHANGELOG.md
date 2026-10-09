# Changelog

All notable changes to this project, newest first. Entries are grouped by UTC date.

## 2026-10-09

### ReflexEnglish web app with guest-first signup — 10:43 UTC
**Summary:** Students can start practising English with photos right away without signing up; sign-up is only asked when they take their first photo or come back a second time, and signed-in students stay logged in.
**Details:** FastAPI + SQLite web app with a Vietnamese UI. Guest progress is kept when the student registers. Registered students stay logged in. Each unique photo is analysed by AI once and the result is shared with everyone. Includes 3 practice levels, Reflex mode and a hands-free auto mode. Uploads are cleaned of location data and photos are private by default.
