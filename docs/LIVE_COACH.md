# Live Coach feasibility study

**Bottom line:** a Live Coach (real-time coaching during play) is **not built** and isn't available in the app. Below is what's possible, what isn't, and under what conditions it might be added in the future.

## What is technically possible
- Gemini's Live API can receive a stream of screen frames and audio and reply in voice with low latency.
- The app already has the building blocks it would need: screen capture (`recording/`), a Gemini connection (`ai/gemini_service.py`), and the Fortnite knowledge and taxonomy (`coaching/`).

## Why it isn't built now
| Constraint | Meaning |
|---|---|
| **Frame rate** | Video models sample about 1–2 frames per second. Edits and piece-control fights take fractions of a second, so live analysis would miss exactly the mistakes this coach is meant to catch. |
| **Latency** | Upload + processing + a voice reply takes seconds. By the time advice arrives, the fight is over. |
| **FPS cost** | Continuous capture, encoding and upload during play cost performance and bandwidth, which goes against the basic requirement of minimal load during a game. |
| **Free Tier** | Live sessions eat quota quickly. A full match won't fit in the free limits. |
| **Epic's rules** | Competitive rules and tournament terms forbid third-party help in real time. Live coaching in Ranked or tournaments could break the rules and put your account at risk. |
| **Distraction** | Voice advice in the middle of a fight hurts concentration more than it helps. |

## When it might make sense in the future
Only if all of the following hold:
1. **Creative training only** (Free Build, an edit course, Zone Wars with friends). Never Ranked, Battle Royale or tournaments.
2. **Opt-in**, off by default, turned on manually for each session.
3. **Voice tips only, between rounds** (not mid-fight), on simple topics such as "you edited without resetting 3 times this round".
4. A clear notice of the FPS cost, and an automatic stop if Fortnite reports a competitive mode.
5. A re-check of Epic's rules at that point in time.

## Conclusion
Coaching after the game (the current mode) catches more, costs less, doesn't hurt FPS, and doesn't risk your account. That's why it's the right approach right now. There's no button in the app pretending a Live Coach exists.
