"""CLI launcher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gws_assistant.cli_app import main

if __name__ == "__main__":
    main()
