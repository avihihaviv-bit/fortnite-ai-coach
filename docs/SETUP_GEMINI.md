# Gemini API key setup

The app works fully without a key (recording, import, preview, metadata, history).
Only AI analysis needs a key.

## Getting a free key
1. Go to **Google AI Studio**: https://aistudio.google.com
2. Sign in with a Google account.
3. Click **Get API key** → **Create API key**.
4. Copy the key (it usually starts with `AIza`).

## Where to paste it
**Settings → Gemini AI** → paste into the field → **Save**.

- The key is stored only in **Windows Credential Manager**. It is never written to files, the database or logs.
- After you save, the field clears and only shows the last 4 characters.
- **Show/Hide** shows the key while you type it.
- **Delete key** removes it from Credential Manager.
- If secure storage isn't available, the key is **not saved**. There is no fallback to plain text.

## Status in the app
| Status | Meaning |
|---|---|
| API key not configured | No key saved. AI analysis is off |
| API key saved, connection not tested yet | A key is saved. Click **Test connection** (it only lists models; no video is sent) |
| Gemini connected | The connection test passed |
| Gemini connection error | The last test failed |

## After saving
1. Click **Test connection**. You should see "✓ Connected".
2. Choose a model (Free Tier only) and a daily request limit.
3. Load a video → **Analyze with Gemini** → check the confirmation screen (number of requests, upload size, today's usage) → Yes.

## Cost and privacy
- **Free Tier only.** The app never turns on billing or switches to a paid model.
- A Gemini Advanced / Google One AI subscription **does not** add API quota.
- On the Free Tier, Google may use your content to improve its products. Only analyze videos you are comfortable sending.
