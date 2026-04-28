"""Gradio launcher."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Google Workspace Assistant in Gradio.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface for Gradio server.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 7860)), help="Port for Gradio server.")
    parser.add_argument("--share", action="store_true", help="Enable public Gradio share link.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    from gws_assistant.gradio_app import main

    main(host=args.host, port=args.port, share=args.share)
