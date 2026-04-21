import time
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Import the demo scripts
import scripts.obs_controller as obs_controller
import scripts.record_cli_auto as record_cli_auto
import scripts.record_gui_auto as record_gui_auto
import scripts.record_web_auto as record_web_auto

def countdown(seconds, message):
    """Display a countdown timer."""
    print(f"\n{message}")
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  Starting!    \n")

def main():
    print("========================================")
    print("      MASTER DEMO RUNNER ORCHESTRATOR    ")
    print("========================================\n")

    # 1. Ensure OBS is running
    obs_controller.ensure_obs_running()
    time.sleep(2)

    # 2. Run CLI Demo
    print("--- STEP 1: CLI DEMO ---")
    record_cli_auto.run()
    
    # 5-second countdown between demos
    countdown(5, "Switching to GUI Demo in:")

    # 3. Run GUI Demo
    print("--- STEP 2: GUI DEMO ---")
    record_gui_auto.run()
    
    # 5-second countdown between demos
    countdown(5, "Switching to WEB Demo in:")

    # 4. Run Web Demo
    print("--- STEP 3: WEB DEMO ---")
    record_web_auto.run()

    print("\n========================================")
    print("      ALL DEMOS COMPLETED SUCCESSFULLY   ")
    print("========================================")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMaster Runner aborted by user.")
    except Exception as e:
        print(f"\n\nAn error occurred in Master Runner: {e}")
