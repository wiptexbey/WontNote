"""
__main__.py — WontNote Package Entry Point
==========================================
Allows running the package directly via `python -m wontnote`.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("WontNote requires Python 3.10 or higher.")

from wontnote.main import main

if __name__ == "__main__":
    main()
