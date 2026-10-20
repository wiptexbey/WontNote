"""
wontnote.py — WontNote Application Entry Point
===============================================
This file is the top-level launcher for the WontNote application.
It delegates to the wontnote package (wontnote/main.py).

Run from the project root:
    python wontnote.py

NOTE: This file and the wontnote/ package share the same base name.
Python resolves imports to the *package* (wontnote/) when both are
present at the same directory level, so there is no import conflict.
This file exists solely as a convenient launch script.
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so the wontnote package is importable
sys.path.insert(0, str(Path(__file__).parent))

from wontnote.main import main  # noqa: E402

if __name__ == "__main__":
    main()
