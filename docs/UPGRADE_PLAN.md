# Audit and upgrade plan: Fortnite AI Coach

Date: 2026-11-17 · State at the time of the audit: phases 1–3 done, 34 tests passing.

## 1. What already works (tested)
| Area | Status |
|---|---|
| Modular architecture (ui / db / ai / video / coaching / core / i18n) | ✅ |
| Dark UI, 12 pages, sidebar, navigation | ✅ |
| Hebrew RTL / English LTR + runtime switching | ✅ |
| SQLite: 13 tables, versioned migrations, cascading deletes | ✅ |
| Settings persistence (language survives a restart) | ✅ |
| Player profile (one row, keyboard and mouse) | ✅ (no page yet) |
| Dashboard computed only from real data ("Not enough data" when there's none) | ✅ |
| Deleting all data / clearing the cache, with confirmation | ✅ |
| The same video is never stored twice (fingerprint) | ✅ |
| Honest Gemini status: "API key not configured" | ✅ |

## 2. What's missing
- Video import, metadata, frame extraction, splitting into segments.
- The Gemini layer (key, connection test, model detection, caching, limits, usage).
- The analysis pipeline itself and the results screen with timestamps.
- The training system, video comparison, progress charts, history.
- An updatable knowledge layer (it has a table but no content).
- Player Profile and Movement pages.
- EXE, GitHub, installation guide.

## 3. What's inaccurate compared with the new requirements, and what was fixed
| Problem | Fix |
|---|---|
| The evaluation rubric was too general (6 items per area) | Expand to a full taxonomy: tunneling, retakes, tarping, double/triple/quad edits, flicks, accuracy per weapon type, strafing, rotations, storm, third parties, endgame |
| A mistake was stored as "description + how to fix" | **Fixed now in the DB:** what you did, what would have been better, why, how to practice, evidence from the video, confidence level, time range |
| Exercises with no category, no "when to level up", and a risk of invented map codes | **Fixed now in the DB:** name, category (warm-up / 1v1 / box fights / zone wars …), `level_up_when`, map **type** only; a code is stored only together with a verification source |
| Long videos would have been cut to the limit | Change: split into segments + a "what was analyzed and what wasn't" report (`coverage` field, already in the DB) |
| A Fortnite-running check was only a "warning" | Change: AI analysis is **blocked** while Fortnite is running (one check at the moment of the click, no monitoring) |
| No knowledge layer with sources and dates | **Fixed now in the DB:** `knowledge` table with source, link, retrieval date, season, `is_current` |
| No Movement page or Player Profile page | Will be added |
| Colors: blue + purple | Change to purple as the main accent + green as the secondary accent (blue stays for info) |

## 4. Order of priorities (the next phases)
1. **Phase 4 – Fortnite knowledge and an expanded rubric (no key needed)**
   A taxonomy of mistakes with stable codes for every area, Movement and Player Profile pages, a basic knowledge pack (principles that don't depend on the season, marked "fundamental"), green accent color.
2. **Phase 5 – Video**
   Validation, ffprobe, frames, splitting into segments, cache, a block while Fortnite is running, a Gameplay Analysis page with preview.
3. **Phase 6 – Gemini**
   Key in Windows Credential Manager, connection test, detection of available models, limits and usage, caching, error handling. Without a key: limited mode that shows clearly what isn't available.
4. **Phase 7 – Professional analysis**
   A prompt per segment built from the rubric, structured JSON + validation, "can't be determined" when there's no evidence, merging segments, a results screen with clickable timestamps.
5. **Phase 8 – Personal coach and training system**
   A profile that updates (strengths, weaknesses, repeated mistakes, improving areas, areas that aren't improving, exercises that bring results), exercises built from the mistakes themselves.
6. **Phase 9 – Comparison and progress**
   Old vs new video of the same game mode, mistakes that disappeared or repeat, trends. No improvement percentages without a reliable calculation.
7. **Phase 10 – Updatable knowledge, cost, security**
   Versioned knowledge packs with a source and date for every fact, an optional "update knowledge" button through Gemini with Google Search (with citations), a usage screen, a security check.
8. **Phase 11 – EXE + GitHub Actions + installation guide**

## 5. Principles that don't change
- No contact with Fortnite: no memory reading, injection, overlay, automation, continuous capture, or changes to Windows/Fortnite settings.
- No fake data, no demo features pretending to be real, no buttons that don't work.
- Season-specific information is never shown without a source and date; outdated information is marked as not current.

## 6. Audit of the new requirement: recording through the app + Live Coach (2026-11-17)

### What already exists
- The database is ready for videos (path + fingerprint, no copy), sessions, reports and mistakes in the full format (what you did / what would have been better / why / how to practice / evidence / confidence).
- `Exercise` and `Mistake` are already structured for "a specific exercise per mistake".
- The ffmpeg check shows that `h264_nvenc` can appear in the list **even when there's no NVIDIA card**, so a real test encode is needed before choosing it.

### What has to change
| Old requirement | New requirement | Decision |
|---|---|---|
| "No automatic recording" | Recording that **the user** starts/stops | Allowed: only on a click or a hotkey, never automatically. A clear indicator while recording |
| Import only | Recording + import | Both, same pipeline |
| — | Global hotkeys | Windows `RegisterHotKey` (a standard OS API, like OBS). No keyboard hook, no contact with the game |
| — | NVENC | Real capability detection (test encode). Order: NVENC → AMD AMF → Intel QSV → x264 (with a warning about CPU load) |
| — | Low CPU load | Capture with `ddagrab` (Desktop Duplication, frames stay on the GPU) + a hardware encoder. **No promise of zero FPS impact** |
| — | Crash safety | Fragmented MP4: the file stays playable even if the recording is cut off |
| Any model | **Free Tier only** | A paid model can't be selected; no billing toggle |
| — | Live Coach in the future | A feasibility document only + an architecture that allows it (a separate capture-source layer). No fake button |

### Known limitations (will appear in the UI and the docs)
- Audio: ffmpeg on Windows doesn't capture system audio without a device such as "Stereo Mix". By default the recording is **video only**; audio is optional when a device is available.
- Exclusive fullscreen: capture may not work. Windowed Fullscreen is recommended.
- The recording itself runs while you play, so it has an FPS cost (small with NVENC, but not zero). AI analysis is blocked while Fortnite is running.

### Updated phase order
4. Fortnite knowledge + expanded evaluation criteria + Movement / Player Profile pages + colors *(now)*
5. Video: import, metadata, segments **+ recording through the app (hotkeys, NVENC, quality, folder, indicator)**
6. Gemini (Free Tier only)
7. Professional analysis: timestamps, what you did / what's better / why / a specific exercise
8. Personal coach and learning from repeated mistakes
9. Comparisons and progress
10. Updatable knowledge, cost, security, **Live Coach feasibility document**
11. EXE + GitHub Actions
