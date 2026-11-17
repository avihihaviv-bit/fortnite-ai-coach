# Architecture

## Principles
1. **Post-session analysis only.** The app never touches Fortnite: no memory reading, no injection,
   no overlay, no automation, no automatic recording, no background processing. Screen recording
   happens only between an explicit user Start and Stop (button or hotkey), via ffmpeg screen capture
   (like OBS). Recordings are not processed until the user loads them; AI analysis runs only when the
   user clicks *Analyze*.
2. **Honest data.** Scores come only from real analysis evidence. No evidence → "Not enough data".
   AI estimates and measured values are always labeled differently. No random or fake statistics.
3. **Works without Gemini.** Every non-AI feature works with no API key. Until a key is saved and
   tested the UI says "API key not configured" / "Gemini not connected" and AI analysis is disabled.
4. **Free first.** Hard usage limits are checked before every request; the model never changes silently;
   billing is never enabled by the app.

## Layers
```
ui/        PySide6 widgets & pages (no business logic)
workers/   QThread workers for user-started jobs (cancellable)
coaching/  rubrics, prompt building, scoring, mistakes, profile, training plans (pure Python)
ai/        Gemini integration: config, key store, service, video analyzer, parser, usage, cache
video/     validation, ffprobe metadata, OpenCV frame sampling, segments + coverage, fingerprints
recording/ capability detection (real test encode), ffmpeg command builder, recorder process,
           global hotkeys (RegisterHotKey), one-shot Fortnite process check
db/        SQLAlchemy models, migrations, repositories (SQLite)
config/    paths and non-secret settings
core/      enums (skills, modes, depth) and the error hierarchy
i18n/      Hebrew (RTL) / English (LTR) catalogs and translator
```
Dependencies point downward only: `ui → workers → coaching/ai/video → db → core/config`.

## Analysis pipeline
1. Validate file (extension, readable, has a video stream).
2. Read metadata with ffprobe (duration, resolution, FPS, codec).
3. Fingerprint (SHA-256 of file chunks + size) → duplicate/cache detection.
4. Prepare: Quick = sampled frames; Standard/Detailed = downscaled, low-FPS, trimmed clip.
5. Show a confirmation dialog (model, size, estimated requests) — nothing is sent without approval.
6. Check usage limits (hard stop) → send to Gemini with a Pydantic response schema.
7. Validate the response; store report, skill scores, mistakes (with timestamps).
8. Recompute player profile and training plan (deterministic, no extra AI request).

## Data location
`%APPDATA%\FortniteAICoach\` — `coach.db` (SQLite), `cache\` (derived frames/clips, deletable), `logs\`.
Original videos are referenced by path, never copied. The API key lives only in Windows Credential Manager.

## Windows EXE
Built with PyInstaller **on Windows** (locally with `build_exe.bat` or via GitHub Actions `windows-latest`).
PyInstaller cannot cross-compile from Linux.
