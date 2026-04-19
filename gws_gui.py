"""GUI launcher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gws_assistant.gui_app import main

if __name__ == "__main__":
    main()
