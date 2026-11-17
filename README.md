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
| 2 | Desktop UI (shell, 12 pages, RTL) | ✅ done |
| 3 | SQLite, settings persistence, data deletion | ✅ done |
| 4 | Video import & processing | ⏳ |
| 5 | Gemini integration (key optional) | ⏳ |
| 6 | Coaching analysis pipeline | ⏳ |
| 7 | Training plans | ⏳ |
| 8 | Progress & history | ⏳ |
| 9 | Cost control & security | ⏳ |
| 10 | Tests & Windows EXE | ⏳ |

## Development
```bash
pip install -r requirements-dev.txt
python -m pytest
```
The Gemini API key is never stored in files — it is entered in *Settings* and kept in Windows Credential Manager.
