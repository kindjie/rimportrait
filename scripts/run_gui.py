"""Launcher entry point for the PyInstaller bundles.

PyInstaller turns its target script into `__main__`, which breaks
the `from . import cli, llm, style` lines inside `rimportrait/gui.py`
(those need the module to be loaded *as* part of the package). This
tiny launcher imports `rimportrait.gui` the normal way so the
relative imports resolve, then calls into its `main()`.
"""

from __future__ import annotations

import sys

from rimportrait.gui import main


if __name__ == "__main__":
  sys.exit(main())
