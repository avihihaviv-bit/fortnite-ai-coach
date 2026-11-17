"""PyInstaller entry point (kept outside the package so imports are absolute)."""

import sys

from fortnite_coach.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
