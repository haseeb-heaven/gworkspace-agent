import argparse
import subprocess
import sys
import time
import webbrowser

import pyautogui
import pygetwindow as gw

import scripts.obs_controller as obs_controller


def run(task="List my Google Sheets files"):
    print(f"--- WEB GUI DEMO AUTOMATION (PyAutoGUI Mode): {task} ---")

    # 1. Start Web Server
    print("Launching Web Server...")
    web_proc = subprocess.Popen(
        [sys.executable, "gws_gui_web.py", "--port", "7860"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    print("Waiting for server to be ready (8s)...")
    time.sleep(8)

    # 2. Open Browser
    url = "http://localhost:7860"
    print(f"Opening browser to {url}...")
    webbrowser.open(url)
    time.sleep(5)

    # 3. Find and Focus Browser Window
    browser_win = None
    titles = ["Google Workspace Assistant", "Gradio", "localhost:7860"]
    for _ in range(10):
        for title in titles:
            wins = [w for w in gw.getWindowsWithTitle(title) if w.isActive == False or w.isActive == True]
            if wins:
                browser_win = wins[0]
                break
        if browser_win:
            try:
                browser_win.activate()
                browser_win.maximize()
                break
            except:
                pass
        time.sleep(1)

    if not browser_win:
        print("Error: Could not find browser window.")
        web_proc.terminate()
        return False

    time.sleep(2)
    print("Starting OBS recording...")
    obs_controller.start_recording()

    # 4. Interact with Gradio UI
    print(f"Typing request: {task}")
    pyautogui.click(browser_win.left + 500, browser_win.top + 300)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")

    pyautogui.write(task, interval=0.05)
    time.sleep(1)

    print("Clicking Run...")
    pyautogui.press("enter")
    pyautogui.click(browser_win.left + 150, browser_win.top + 450)

    # 5. Wait for results
    print("Waiting 15 seconds for results and visual feedback...")
    time.sleep(15)

    print("Stopping OBS recording...")
    obs_controller.stop_recording()

    # Cleanup
    web_proc.terminate()
    print("Web GUI PyAuto Demo Done.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="List my Google Sheets files")
    args = parser.parse_args()
    run(task=args.task)
