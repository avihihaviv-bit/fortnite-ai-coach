# Fortnite AI Coach

A personal Fortnite coach for Windows. You record (or import) a game, and after you **finish playing** the coach analyzes the video with Google Gemini and gives you:

- **Real mistakes with timestamps:** what you did, what would have been better, why, a specific drill, evidence from the video, and a confidence level.
- **Levels and XP** for every skill, plus an overall level. XP comes only from good plays the coach saw in the video.
- **A personal training plan** built from the mistakes that repeat for you, with an exercise, a goal, a time, and when to raise the difficulty.
- **Progress over time:** charts, weekly and monthly tables, mistakes that got fixed, personal records, and comparing two games.

**Safe for the game:** no contact with Fortnite (no memory reading, injection, overlay or automation). Recording is ordinary screen capture, only when you start it. Analysis runs only after the game.

## Installation
1. Download `FortniteAICoach-Setup-<version>.exe` from the repo's **Releases** page (or from **Actions** → the latest successful build → Artifacts).
2. Run it. If you see "Windows protected your PC", click **More info**, then **Run anyway** (the installer isn't signed with a paid certificate).
3. Open "Fortnite AI Coach" from the Start Menu.

No Python or ffmpeg needed; everything is included. More in [docs/INSTALL.md](docs/INSTALL.md).

## First run (5 minutes)
1. **Gemini key (free):** https://aistudio.google.com → Get API key → copy. In the app: **Settings → Gemini AI** → paste → **Save** → **Test connection**. ([guide](docs/SETUP_GEMINI.md))
   The key is stored only in Windows Credential Manager. Don't send it to anyone.
2. **Settings → Recording → Check hardware:** shows whether NVENC (NVIDIA) or another encoder is available.
3. **Before playing:** open the app, set Fortnite to Windowed Fullscreen, and start recording with `Ctrl+Shift+F9` (stop with `Ctrl+Shift+F10`). The app stays next to the clock.
4. **After playing:** close Fortnite → Gameplay Analysis → "Load this recording" → choose the game mode → **Analyze with Gemini** → confirm.
5. Read the report in **History**, do the exercises in **Training Plan**, and track your progress in **Progress**.

## Cost and privacy
- **Free Tier only.** A hard daily limit, a confirmation before every send, and a cache so the same video doesn't cost twice. The app never turns on billing.
- What goes to Google: a list of models (connection test), a compressed copy of the analyzed part of the video (only after you confirm), and a season search (only after you confirm). There's no telemetry.
- Full details in [docs/PRIVACY.md](docs/PRIVACY.md). Live Coach (in-game coaching) isn't available. Why: [docs/LIVE_COACH.md](docs/LIVE_COACH.md).

## Status
| Phase | Area | Status |
|---|---|---|
| 1–2 | Architecture, dark UI, Hebrew RTL / English | ✅ |
| 3–4 | Database, player profile, Fortnite taxonomy and knowledge | ✅ |
| 5 | Recording through the app (hotkeys, NVENC), video import, secure key | ✅ |
| 6–7 | Gemini (Free Tier), analysis with timestamps, report, levels and XP | ✅ |
| 8 | Personal training plan and measuring how well training works | ✅ |
| 9 | Progress, records, comparisons | ✅ |
| 10 | Usage and cost, updatable knowledge with sources, privacy and security, Live Coach study | ✅ |
| Installer | PyInstaller + Inno Setup, built and tested automatically on Windows | ✅ |

Not yet tested on a real gaming computer with a real key: NVENC recording during Fortnite and analysis of a real game. Everything else is checked automatically on Windows on every build.

## Development
```bash
pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest
```
The installer is built in GitHub Actions on every push (`.github/workflows/build-windows.yml`), or locally with `build_exe.bat`. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
