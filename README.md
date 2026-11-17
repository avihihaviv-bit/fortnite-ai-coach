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
| 5 | Video import + in-app recording (hotkeys, NVENC) | ⏳ |
| 6 | Gemini integration (Free Tier only, key optional) | ⏳ |
| 7 | Professional analysis with timestamps | ⏳ |
| 8 | Personal coach & training plans | ⏳ |
| 9 | Comparison, progress, history | ⏳ |
| 10 | Knowledge updates, cost control, security, Live Coach feasibility | ⏳ |
| 11 | Tests & Windows EXE | ⏳ |

See `docs/UPGRADE_PLAN.md` for the audit and roadmap.


## Development
```bash
pip install -r requirements-dev.txt
python -m pytest
```
The Gemini API key is never stored in files — it is entered in *Settings* and kept in Windows Credential Manager.
