import argparse
import os
import subprocess
import time

import pygetwindow as gw

import scripts.obs_controller as obs_controller


def run(task="Show my last 5 emails"):
    print(f"--- CLI DEMO AUTOMATION: {task} (New Window) ---")

    # Path for signal file to know when task is done
    signal_file = os.path.join(os.getcwd(), "cli_done.tmp")
    if os.path.exists(signal_file):
        try:
            os.remove(signal_file)
        except:
            pass

    # 1. Launch new PowerShell window
    activate_script = r"..\..\henv\Scripts\Activate.ps1"
    task_cmd = f"python gws_cli.py --task '{task}' --read-only --no-sandbox"
    full_cmd = f"& '{activate_script}'; cd '{os.getcwd()}'; {task_cmd}; New-Item -Path '{signal_file}' -ItemType File; Start-Sleep -s 5; exit"

    print("Launching new terminal window...")
    subprocess.Popen(
        [
            "powershell.exe",
            "-Command",
            f'start-process powershell.exe -ArgumentList "-NoExit", "-Command", "{full_cmd}"',
        ]
    )

    # 2. Focus the new window
    time.sleep(3)
    ps_windows = [w for w in gw.getWindowsWithTitle("PowerShell") if w.isActive == False]
    if ps_windows:
        try:
            ps_windows[0].activate()
        except:
            pass

    print("Starting OBS recording...")
    obs_controller.start_recording()

    # 3. Wait INFINITELY until signal file exists
    print("Monitoring task progress (waiting for completion)...")
    start_time = time.time()
    while not os.path.exists(signal_file):
        time.sleep(1)
        if time.time() - start_time > 300:
            print("Error: CLI task timed out.")
            return False

    print("Task completed! Stopping recording...")
    time.sleep(2)
    obs_controller.stop_recording()

    # Cleanup with retry to avoid lock
    time.sleep(3)
    if os.path.exists(signal_file):
        try:
            os.remove(signal_file)
        except:
            pass

    print("CLI Demo Action Finished.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="Show my last 5 emails")
    args = parser.parse_args()
    run(task=args.task)
