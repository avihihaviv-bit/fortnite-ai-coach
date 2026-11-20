# Live Coach (experimental)

Live Coach shows a short tip in the **top-left corner** while you play. It's **off by default**. To turn it on: Settings → Live Coach → read the limits → tick the box → Save.

## How it works
- Every 2 seconds the app takes a small screenshot (1280 px wide, using the same capture as recording). The screenshots are kept in a temporary folder and deleted when Live Coach stops.
- Every *N* seconds (default 30) the last few screenshots go to Gemini in one request. The answer is a tip of up to 12 words, or "NONE" when there's nothing useful to say (menus, lobby, loading). On "NONE", nothing is shown.
- The tip appears in a window that doesn't take focus and doesn't capture the mouse ("click-through"), then disappears after a few seconds.

## Starting and stopping
On the "Record" card, choose: **Record video**, **Record video + Live Coach**, or **Live Coach only**. The Start button and the start/stop hotkeys follow that choice. There's also a separate hotkey (default `Ctrl+Shift+F11`) and an item in the tray menu.

## Honest limits
| Limit | What it means |
|---|---|
| 1 screenshot every 2 s | Sees situations and habits (protection, height, heals, storm, materials, pre-fire), not edits that take a fraction of a second. |
| Delay of ~5–20 s | Capture + network + model. The tip is about what just happened, not about this exact moment. |
| Free Tier | Each tip is one request from the same daily quota as video analysis. At 30 s that's up to 120 requests per hour of play. Stops automatically at the daily limit you set, or when Google says the quota is used up. |
| FPS | Low-rate screen capture, small cost. |
| Display | Fortnite must be in Windowed Fullscreen for the tip to show on top of the game. |
| **Epic's rules** | **Practice only** (Creative, Box Fights, Zone Wars with friends). Not in Ranked or tournaments: real-time help from a third-party tool can break the competitive rules. |

## What it does NOT do
It doesn't read game memory, doesn't send input, doesn't automate anything, and doesn't keep the screenshots. It only looks at the screen, like a viewer.

The full analysis after the game (from a video) is still far more precise. Live Coach is an addition, not a replacement.
