# Fortnite AI Coach

A personal, post-session Fortnite coach for Windows. Pick a finished gameplay or Creative training
recording, and the coach analyzes it (with Google Gemini) to find real mistakes, score your skills from
evidence, track recurring weaknesses and build a personalized training plan.

**Game safety:** the app never interacts with Fortnite — no capture, no memory reading, no injection,
no background processing. Analysis runs only when you start it, after you have finished playing.

## Status
Under active development — see `docs/ARCHITECTURE.md` and the phase list below.

| Phase | Area | Status |
|---|---|---|
| 1 | Project structure & architecture | ✅ done |
| 2 | Desktop UI (shell, pages, RTL) | ✅ done |
| 3 | SQLite, settings persistence, data deletion | ✅ done |
| 4 | Fortnite taxonomy, knowledge base, Movement & Player Profile pages | ✅ done |
| 5 | Video import + in-app recording (hotkeys, NVENC) + secure API key field | ✅ done (recording to be verified on Windows) |
| 6 | Gemini integration (Free Tier only, connection test, limits, cache) | ✅ done (mocked; real key pending) |
| 7 | Professional analysis with timestamps + levels/XP + History report | ✅ done (mocked; real key pending) |
| 8 | Personal training plan (from your mistakes), completion tracking, measured training effect | ✅ done |
| 9 | Comparison, progress, history | ⏳ |
| 10 | Knowledge updates, cost control, security, Live Coach feasibility | ⏳ |
| 11 | Windows installer (PyInstaller + Inno Setup, CI build + self-test) | ✅ build system ready (first Windows build pending) |

See `docs/UPGRADE_PLAN.md` for the audit and roadmap.


## Install (Windows)
Download `FortniteAICoach-Setup-<version>.exe` and run it. See `docs/INSTALL.md`.

## Development
```bash
pip install -r requirements-dev.txt
python -m pytest
```
Build the installer locally with `build_exe.bat` (Python 3.12 + Inno Setup 6), or let GitHub Actions build it.
The Gemini API key is never stored in files — it is entered in *Settings* and kept in Windows Credential Manager.
