"""Entry point: ``python -m fortnite_coach``."""

import sys


def main() -> int:
    from fortnite_coach.app import run

    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
