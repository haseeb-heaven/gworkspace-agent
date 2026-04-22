import ctypes
import time
import subprocess
import os

# Windows Virtual Key Codes
VK_CONTROL = 0x11
VK_R = 0x52
VK_S = 0x53
KEYEVENTF_KEYUP = 0x02

def start_recording():
    """Trigger OBS Start Hotkey (Ctrl + R)"""
    print("OBS: Sending Start Recording command (Ctrl+R)...")
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl Press
    ctypes.windll.user32.keybd_event(VK_R, 0, 0, 0)        # R Press
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(VK_R, 0, KEYEVENTF_KEYUP, 0)    # R Release
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)# Ctrl Release
    print("OBS: Command sent. Waiting 2s for encoder initialization...")
    time.sleep(2)

def stop_recording():
    """Trigger OBS Stop Hotkey (Ctrl + S)"""
    print("OBS: Sending Stop Recording command (Ctrl+S)...")
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl Press
    ctypes.windll.user32.keybd_event(VK_S, 0, 0, 0)        # S Press
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)    # S Release
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)# Ctrl Release
    print("OBS: Command sent. Waiting 3s for file flush...")
    time.sleep(3)

def ensure_obs_running():
    """Check for 'obs64.exe' and if not found, start it."""
    obs_process = "obs64.exe"
    obs_path = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
    
    try:
        output = subprocess.check_output('tasklist /FI "IMAGENAME eq obs64.exe"', shell=True).decode(errors='ignore')
        if obs_process.lower() not in output.lower():
            print(f"OBS: {obs_process} not running. Starting from {obs_path}...")
            if os.path.exists(obs_path):
                subprocess.Popen([obs_path], cwd=os.path.dirname(obs_path))
                print("OBS: OBS Studio started.")
                time.sleep(10)
            else:
                print(f"OBS: ERROR - Could not find OBS at {obs_path}")
        else:
            print("OBS: OBS Studio is already running.")
    except Exception as e:
        print(f"OBS: Error in ensure_obs_running: {e}")

def get_current_video_files():
    video_dir = r"C:\Users\hasee\Videos"
    if os.path.exists(video_dir):
        try:
            return set(os.listdir(video_dir))
        except Exception:
            return set()
    return set()

def verify_recording(prev_files):
    """Check if a new video file appeared in the Videos folder."""
    print("OBS: Verifying recording...")
    video_dir = r"C:\Users\hasee\Videos"
    if not os.path.exists(video_dir):
        print(f"OBS: ERROR - Video directory not found: {video_dir}")
        return False, prev_files
    
    # Check multiple times over 5 seconds for slow disk writes
    for _ in range(5):
        current_files = set(os.listdir(video_dir))
        new_files = current_files - prev_files
        new_videos = [f for f in new_files if f.lower().endswith(('.mp4', '.mkv', '.mov', '.flv'))]
        
        if new_videos:
            print(f"OBS: SUCCESS! New recording found: {new_videos[0]}")
            return True, current_files
        time.sleep(1)
        
    print("OBS: WARNING - No new video file detected in C:\\Users\\hasee\\Videos")
    return False, prev_files

if __name__ == "__main__":
    ensure_obs_running()
