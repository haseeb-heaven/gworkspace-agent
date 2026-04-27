import argparse
import os
import subprocess
import sys
import time
import webbrowser

import scripts.obs_controller as obs_controller


# This script is intended to be used when the agent itself (using chrome-devtools)
# performs the interaction.
def run(task="List my Google Sheets files"):
    print(f"--- WEB GUI DEMO AUTOMATION (DevTools/Agent Mode): {task} ---")

    done_file = os.path.join(os.getcwd(), "web_done.tmp")
    if os.path.exists(done_file):
        try:
            os.remove(done_file)
        except:
            pass

    # 1. Start Web Server
    print("Launching Web Server...")
    web_proc = subprocess.Popen(
        [sys.executable, "gws_gui_web.py", "--port", "7860"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    print("Waiting for server to be ready (8s)...")
    time.sleep(8)

    # 2. Open Browser (so the user/recorder can see it)
    url = "http://localhost:7860"
    print(f"Opening browser to {url} for recording...")
    webbrowser.open(url)
    time.sleep(5)

    print("Starting OBS recording...")
    obs_controller.start_recording()

    print("\n[AGENT_SIGNAL] WEB_SERVER_READY_AT_7860")
    print(f">>> Agent should now perform the task: '{task}'")
    print(">>> Use Chrome DevTools tools to interact.")
    print(">>> Create 'web_done.tmp' when finished.")

    # 3. Wait for Signal
    start_time = time.time()
    while not os.path.exists(done_file):
        time.sleep(1)
        if time.time() - start_time > 600:  # 10 min for devtools work
            print("Error: Web interaction timed out.")
            break

    print("Agent interaction complete. Waiting 5s for UI to settle...")
    time.sleep(5)

    print("Stopping OBS recording...")
    obs_controller.stop_recording()

    # Cleanup
    web_proc.terminate()
    if os.path.exists(done_file):
        try:
            os.remove(done_file)
        except:
            pass

    print("Web GUI DevTools Demo Action Finished.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="List my Google Sheets files")
    args = parser.parse_args()
    run(task=args.task)
