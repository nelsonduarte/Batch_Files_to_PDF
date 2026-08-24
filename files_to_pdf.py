#!/usr/bin/env python3
"""Launcher: `python files_to_pdf.py ...` runs the converter.

The modules live next to this file, so putting this folder on sys.path is all
that is needed before importing them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
