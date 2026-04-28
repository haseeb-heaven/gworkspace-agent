import argparse
import os
import sys
import time

# Add the project root to sys.path to allow absolute imports of scripts
sys.path.insert(0, os.getcwd())

import scripts.obs_controller as obs_controller
import scripts.record_cli_auto as record_cli_auto
import scripts.record_gui_auto as record_gui_auto
import scripts.record_web_dev as record_web_dev
import scripts.record_web_pyauto as record_web_pyauto


def main():
    parser = argparse.ArgumentParser(description="GWS Agent Demo Orchestrator")
    parser.add_argument("--cli", action="store_true", help="Run CLI demo")
    parser.add_argument("--gui", action="store_true", help="Run Desktop GUI demo")
    parser.add_argument("--webui-dev", action="store_true", help="Run Web GUI demo (DevTools/Agent mode)")
    parser.add_argument("--webui-pyauto", action="store_true", help="Run Web GUI demo (PyAutoGUI mode)")
    parser.add_argument("--task", type=str, help="Custom task description for the demos")
    args = parser.parse_args()

    # If no flags, run basic automated set
    if not (args.cli or args.gui or args.webui_dev or args.webui_pyauto):
        args.cli = args.gui = args.webui_pyauto = True

    print("=" * 40)
    print("      REAL-WORLD DEMO ORCHESTRATOR")
    print("=" * 40)

    print("\nEnsuring OBS Studio is running...")
    obs_controller.ensure_obs_running()

    # 1. CLI Demo
    if args.cli:
        task = args.task or "Show my last 5 emails"
        print(f"\n--- STEP 1: CLI DEMO ({task}) ---")
        prev_files = obs_controller.get_current_video_files()
        record_cli_auto.run(task=task)
        success, _ = obs_controller.verify_recording(prev_files)
        if not success:
            print("\n[!] FAILURE: CLI Demo failed. Stopping.")
            sys.exit(1)
        print("\n[✓] CLI Demo Success.")
        if args.gui or args.webui_dev or args.webui_pyauto:
            print("Switching in 10s...")
            time.sleep(10)

    # 2. Desktop GUI Demo
    if args.gui:
        task = args.task or "Show my last 5 files from Google drive"
        print(f"\n--- STEP 2: DESKTOP GUI DEMO ({task}) ---")
        prev_files = obs_controller.get_current_video_files()
        res = record_gui_auto.run(task=task)
        if not res:
            print("\n[!] FAILURE: GUI Demo failed during execution.")
            obs_controller.stop_recording()  # Failsafe
            sys.exit(1)

        success, _ = obs_controller.verify_recording(prev_files)
        if not success:
            print("\n[!] FAILURE: GUI Demo failed to produce a recording.")
            sys.exit(1)
        print("\n[✓] Desktop GUI Demo Success.")
        if args.webui_dev or args.webui_pyauto:
            print("Switching in 10s...")
            time.sleep(10)

    # 3. Web GUI PyAuto Demo
    if args.webui_pyauto:
        task = args.task or "List my Google Sheets files"
        print(f"\n--- STEP 3: WEB GUI PYAUTO DEMO ({task}) ---")
        prev_files = obs_controller.get_current_video_files()
        res = record_web_pyauto.run(task=task)
        if not res:
            print("\n[!] FAILURE: Web PyAuto Demo failed during execution.")
            obs_controller.stop_recording()
            sys.exit(1)

        success, _ = obs_controller.verify_recording(prev_files)
        if not success:
            print("\n[!] FAILURE: Web PyAuto Demo failed to produce a recording.")
            sys.exit(1)
        print("\n[✓] Web GUI PyAuto Demo Success.")
        if args.webui_dev:
            print("Switching in 10s...")
            time.sleep(10)

    # 4. Web GUI DevTools Demo
    if args.webui_dev:
        task = args.task or "List my Google Sheets files"
        print(f"\n--- STEP 4: WEB GUI DEVTOOLS DEMO ({task}) ---")
        prev_files = obs_controller.get_current_video_files()
        res = record_web_dev.run(task=task)
        if not res:
            print("\n[!] FAILURE: Web Dev Demo failed during execution.")
            obs_controller.stop_recording()
            sys.exit(1)

        success, _ = obs_controller.verify_recording(prev_files)
        if not success:
            print("\n[!] FAILURE: Web Dev Demo failed to produce a recording.")
            sys.exit(1)
        print("\n[✓] Web GUI DevTools Demo Success.")

    print("\n" + "=" * 40)
    print("      ALL SELECTED DEMOS COMPLETED")
    print("=" * 40)

    print("Check 'C:\\Users\\hasee\\Videos' for your recordings.")


if __name__ == "__main__":
    main()
