import ctypes
import time
import subprocess
import os

# Windows Virtual Key Codes
VK_CONTROL = 0x11
VK_F11 = 0x7A
VK_F12 = 0x7B
KEYEVENTF_KEYUP = 0x02

def start_recording():
    """Trigger OBS Start Hotkey (Ctrl + F12)"""
    print("OBS: Sending Start Recording command (Ctrl+F12)...")
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl Press
    ctypes.windll.user32.keybd_event(VK_F12, 0, 0, 0)      # F12 Press
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(VK_F12, 0, KEYEVENTF_KEYUP, 0)  # F12 Release
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl Release

def stop_recording():
    """Trigger OBS Stop Hotkey (Ctrl + F11)"""
    print("OBS: Sending Stop Recording command (Ctrl+F11)...")
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl Press
    ctypes.windll.user32.keybd_event(VK_F11, 0, 0, 0)      # F11 Press
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(VK_F11, 0, KEYEVENTF_KEYUP, 0)  # F11 Release
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl Release

def ensure_obs_running():
    """Check for 'obs64.exe' and if not found, start 'C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe'."""
    obs_process = "obs64.exe"
    obs_path = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
    
    try:
        # Use tasklist to check if OBS is running
        output = subprocess.check_output('tasklist /FI "IMAGENAME eq obs64.exe"', shell=True).decode(errors='ignore')
        if obs_process.lower() not in output.lower():
            print(f"OBS: {obs_process} not running. Starting from {obs_path}...")
            if os.path.exists(obs_path):
                # Start OBS and don't wait for it
                subprocess.Popen([obs_path], cwd=os.path.dirname(obs_path))
                print("OBS: OBS Studio started.")
                time.sleep(5)  # Wait for it to load
            else:
                print(f"OBS: ERROR - Could not find OBS at {obs_path}")
        else:
            print("OBS: OBS Studio is already running.")
    except Exception as e:
        print(f"OBS: Error in ensure_obs_running: {e}")

if __name__ == "__main__":
    # Test functions
    ensure_obs_running()
    # start_recording()
    # time.sleep(2)
    # stop_recording()
