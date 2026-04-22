
import time
import subprocess
import os
import sys
import argparse
import pyautogui
import pygetwindow as gw
import scripts.obs_controller as obs_controller

def run(task="Show my last 5 files from Google drive"):
    print(f"--- DESKTOP GUI DEMO AUTOMATION: {task} ---")
    
    log_file = os.path.join(os.getcwd(), "logs", "gws_assistant.log")
    start_offset = 0
    if os.path.exists(log_file):
        start_offset = os.path.getsize(log_file)

    print("Launching GUI...")
    gui_proc = subprocess.Popen([sys.executable, "gws_gui.py"])
    time.sleep(12)
    
    # 1. Focus GUI
    gui_win = None
    for _ in range(5):
        wins = [w for w in gw.getWindowsWithTitle('Google Workspace Assistant') if 'Assistant' in w.title]
        if wins:
            gui_win = wins[0]
            try:
                gui_win.activate()
                gui_win.maximize() # Maximize for predictable coords
                break
            except: pass
        time.sleep(2)
        
    if not gui_win:
        print("Error: Could not find GUI window.")
        return False

    time.sleep(2)
    print("Starting OBS recording...")
    obs_controller.start_recording()
    
    # 2. Type Request
    # Coords for Maximized 1920x1080 window (rough estimates)
    # Input box is roughly at top
    pyautogui.click(gui_win.left + 500, gui_win.top + 150) 
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('backspace')
    
    print(f"Typing: {task}")
    pyautogui.write(task, interval=0.05)
    time.sleep(1)
    
    # 3. Click Analyze
    print("Clicking Analyze...")
    pyautogui.click(gui_win.left + 150, gui_win.top + 280)
    
    # Wait for analyze result
    time.sleep(12)
    
    # 4. Click Execute
    print("Clicking Execute...")
    pyautogui.click(gui_win.left + 830, gui_win.top + 280)
    
    # 5. Wait exactly 10 seconds
    print("Waiting 10 seconds for visual feedback...")
    time.sleep(10)
    
    print("Stopping OBS recording...")
    obs_controller.stop_recording()
    
    gui_proc.terminate()
    print("Desktop GUI Demo Done.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="Show my last 5 files from Google drive")
    args = parser.parse_args()
    run(task=args.task)
