#!/usr/bin/env python3
"""Lightwrite entrypoint."""
import os
import sys

# Allow running from source tree: src/ on sys.path
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from lightwrite.app import main

if __name__ == "__main__":
    main()
