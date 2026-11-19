# Privacy and data: Fortnite AI Coach

## What stays on your computer only
| What | Where |
|---|---|
| Database (analyses, mistakes, XP, training plan, settings) | `%APPDATA%\FortniteAICoach\coach.db` |
| Frames and compressed copies for analysis | `%APPDATA%\FortniteAICoach\cache\` |
| Error log (keys are always redacted) | `%APPDATA%\FortniteAICoach\logs\app.log` |
| Gemini API key | Windows Credential Manager only (entry `FortniteAICoach`) |
| Your recordings | The folder you chose. The app never copies or deletes them |

The app has no server of its own and sends no telemetry or statistics anywhere.

## What gets sent to Google, and only when
| Action | What's sent | When |
|---|---|---|
| **Test connection** | A request for the list of models (no video) | When you click the button |
| **Analysis** | A compressed copy of the analyzed part of the video + the instructions to the coach | Only after you click Analyze and **approve** the confirmation screen |
| **Update knowledge** | A search request about the current season (no video, no personal data) | Only when you click the button and approve |

There's no background sending, no automatic sending, and no sending while Fortnite is running.

## Free Tier: important to know
- In the Gemini API Free Tier, Google may use the content you send to improve its products, and human reviewers may see it. So only analyze videos you're comfortable sending.
- Videos uploaded to Gemini are kept by Google for about 48 hours and then deleted automatically. **Settings → Delete all analysis data** also asks Google to delete files you uploaded (when the key is connected).
- The app uses only the Free Tier models it lists, never turns on billing, and never switches to a paid model.
- The app **can't see** whether billing is enabled on your Google project. If it is, Google may charge according to its terms. The daily limit in Settings is a hard cap: the app checks it before sending.

## Deleting data
- **Delete one session:** History → Delete session (the report, mistakes and XP from that session).
- **Delete all analysis data:** Settings → Your data. The settings, profile and key stay.
- **Delete the key:** Settings → Gemini AI → Delete key.
- **Remove everything:** uninstall the app, delete the folder `%APPDATA%\FortniteAICoach`, and delete the `FortniteAICoach` entry in Windows Credential Manager.

## Contact with the game
None. No memory reading, no injection, no overlay, no automation, and no changes to Windows or Fortnite settings. Recording is ordinary screen capture (like OBS), only between a start and a stop that you trigger.
