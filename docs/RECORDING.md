# Recording through the app (Windows)

## What it does
- Starts and stops **only** when you click a button or press a hotkey. There's no automatic recording, no monitoring of the game, and no contact with the Fortnite process.
- Captures the screen with **ffmpeg**:
  - `ddagrab` (Desktop Duplication): frames stay on the graphics card.
  - `gdigrab` as a fallback.
- Encoding:
  - **NVIDIA NVENC** if it really works on your PC (checked with a short test encode).
  - Otherwise AMD AMF, then Intel QSV, then x264 on the CPU (with a load warning).
- Files: fragmented MP4. If the PC crashes mid-recording, the file stays playable.

## FPS impact
Recording **always** costs some performance. With NVENC and native resolution it's usually small, but it isn't zero. To lower it:
- Native resolution (with NVENC/AMF there's no CPU scaling).
- 30 FPS instead of 60.
- "Low" quality.

## Requirements
- **ffmpeg** with `ddagrab` support (version 6.1 or newer, Windows build). Easy install:
  ```
  winget install Gyan.FFmpeg
  ```
  Or set the path to `ffmpeg.exe` with the `FORTNITE_COACH_FFMPEG` environment variable.
- For NVENC: an NVIDIA card with an up-to-date driver.

## Known limitations
- **Display mode:** run Fortnite in **Windowed Fullscreen**. Exclusive fullscreen may not be captured.
- **Audio:** by default the recording is **video only**. Audio requires a device such as "Stereo Mix" (enable it in Windows sound settings) and selecting it in Settings → Recording.
- **Hotkeys:** registered through the standard Windows mechanism (`RegisterHotKey`, the same one OBS uses).
  - If another program already uses the same combination, registration fails. Pick a different combination.
  - A combination must include Ctrl/Alt/Shift, so it doesn't take over a plain game key.

## After recording
The file is **not** processed automatically, because you may still be in a match. A "Load this recording" button appears. Click it once you've finished playing.
