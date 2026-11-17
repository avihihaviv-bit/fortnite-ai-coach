# PyInstaller spec for Fortnite AI Coach.
# Build (Windows):  pyinstaller packaging/fortnite_coach.spec --noconfirm
# Output: dist/FortniteAICoach/FortniteAICoach.exe  (onedir: fast start, fewer AV false positives)
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
PKG = ROOT / "src" / "fortnite_coach"
IS_WIN = sys.platform == "win32"

# Every runtime data file, placed under fortnite_coach/... so config.paths.resource_path works unchanged.
DATA_PATTERNS = ["i18n/*.json", "ui/*.qss", "knowledge/*.json", "assets/*.png", "assets/*.ico"]
datas = []
for pattern in DATA_PATTERNS:
    for f in sorted(PKG.glob(pattern)):
        datas.append((str(f), str(Path("fortnite_coach") / f.parent.relative_to(PKG))))

# Bundled ffmpeg/ffprobe -> <bundle>/ffmpeg/ (matches video.ffmpeg_tools._bundled_dir).
binaries = []
ffmpeg_dir = ROOT / "vendor" / "ffmpeg"
for name in ("ffmpeg", "ffprobe"):
    exe = ffmpeg_dir / (name + (".exe" if IS_WIN else ""))
    if exe.is_file():
        binaries.append((str(exe), "ffmpeg"))
if (ffmpeg_dir / "FFMPEG_LICENSE.txt").is_file():
    datas.append((str(ffmpeg_dir / "FFMPEG_LICENSE.txt"), "ffmpeg"))
if IS_WIN and len(binaries) != 2:
    raise SystemExit("vendor/ffmpeg/ffmpeg.exe and ffprobe.exe are missing - run packaging/fetch_ffmpeg.ps1 first")

hiddenimports = [
    "keyring.backends.Windows" if IS_WIN else "keyring.backends.fail",
    "sqlalchemy.dialects.sqlite",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
]

# Never bundle Qt modules the app does not use (size + attack surface).
excludes = [
    "tkinter", "matplotlib", "IPython", "pytest", "pytestqt",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtDesigner", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtHttpServer",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtStateMachine", "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtOpenGLWidgets",
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
# Qt plugins drag in QML/Quick/PDF/virtual-keyboard libraries the app never uses: drop them.
_DROP = ("qt6quick", "qt6qml", "qt6pdf", "virtualkeyboard", "qt6waylandclient", "qt6wlshell",
         "plugins/platforminputcontexts", "plugins/imageformats/qpdf", "plugins/wayland", "qml/")


def _keep(entry):
    dest = entry[0].replace("\\", "/").lower()
    return not any(d in dest for d in _DROP)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FortniteAICoach",
    icon=str(PKG / "assets" / "app.ico"),
    version=str(ROOT / "packaging" / "version_info.txt") if IS_WIN else None,
    console=False,          # windowed app: no console window
    disable_windowed_traceback=False,
    upx=False,              # UPX-compressed binaries trigger antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FortniteAICoach")
