# Installing Fortnite AI Coach on Windows

## Requirements
- Windows 10 or 11, 64-bit.
- No Python and no separate ffmpeg needed. Everything is bundled in the installer.
- No administrator rights needed. The app installs only for your user.

## Installing
1. Download `FortniteAICoach-Setup-<version>.exe`:
   - **Releases** in the repo (a permanent page), or
   - **Actions** → the latest run with ✓ → scroll down → **Artifacts** → download and unzip.
2. Run the file.
3. **"Windows protected your PC" warning:** this appears because the installer isn't signed with a paid code-signing certificate. Click **More info**, then **Run anyway**.
4. Pick a language, choose whether you want a desktop shortcut, and click Install.
5. The app opens from the **Start Menu**, "Fortnite AI Coach".

## Where things are stored
| What | Where |
|---|---|
| The program | `%LOCALAPPDATA%\Programs\Fortnite AI Coach` |
| Database, settings, cache, logs | `%APPDATA%\FortniteAICoach` |
| Gemini key | Windows Credential Manager (entry `FortniteAICoach`) |
| Recordings | The folder you chose in Settings → Recording (default `Videos\Fortnite AI Coach`) |

## Upgrading
Run a newer Setup over the existing installation. Your data, settings and key are kept.

## Uninstalling
Windows Settings → Apps → Fortnite AI Coach → Uninstall.
Only the program is removed. **Your data and key are kept**, so you don't lose your history if you reinstall.
To delete them too, delete the folder `%APPDATA%\FortniteAICoach` and the `FortniteAICoach` entry in Credential Manager.

## Troubleshooting
- **Health check:** run in a command prompt:
  ```
  "%LOCALAPPDATA%\Programs\Fortnite AI Coach\FortniteAICoach.exe" --self-test --out "%USERPROFILE%\Desktop\selftest.json"
  ```
  This creates a file on the desktop showing what works: resources, database, ffmpeg, secure storage.
- **Error log:** `%APPDATA%\FortniteAICoach\logs\app.log`. Keys are never written to it.
- **Opening it a second time** brings the window that's already open to the front. Only one copy runs at a time.

## Building the installer yourself
- **Automatically:** every push to GitHub builds the installer in GitHub Actions on a Windows machine. The build runs the tests, builds, self-tests the EXE, installs it, self-tests again, and uninstalls.
- **On your computer:** install Python 3.12 and Inno Setup 6, then double-click `build_exe.bat`.

## Checklist after installation
1. The app opens from the Start Menu, in Hebrew, with the dark design.
2. Settings → About → **Run health check** → "✓ Everything required works".
3. Settings → Recording → **Check hardware** → working encoders are listed (NVENC on an NVIDIA card).
4. Record 20 seconds with `Ctrl+Shift+F9` / `Ctrl+Shift+F10` → "Load this recording" → video details appear.
5. Settings → Gemini AI → paste the key → Save → Test connection → "✓ Connected".
6. Analyze a short recording → a report opens in History.
7. Close and reopen the app → everything is still there.
