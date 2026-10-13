"""Double-click to start Stackyard (no console window)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui  # noqa: E402

if __name__ == "__main__":
    ui.main()
