
import os
import time
import ctypes
import random
import sys
from pathlib import Path

# Add the project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from scripts.obs_controller import start_recording, stop_recording
except ImportError:
    # Fallback if scripts is not a package
    sys.path.append(str(PROJECT_ROOT / "scripts"))
    from obs_controller import start_recording, stop_recording

# Windows Virtual-Key Codes
VK_RETURN = 0x0D
VK_SHIFT = 0x10

def press_key(vk_code, shift=False):
    """Simulates a key press with optional shift modifier."""
    if shift:
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 0, 0)
    
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0) # Key down
    time.sleep(random.uniform(0.02, 0.05))
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0) # Key up
    
    if shift:
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 2, 0)

def type_string_realistic(text):
    """Types a string with realistic delays and shift support."""
    for char in text:
        res = ctypes.windll.user32.VkKeyScanW(ord(char))
        vk_code = res & 0xFF
        shift_state = (res >> 8) & 0xFF
        
        # shift_state: bit 0 is shift, bit 1 is ctrl, bit 2 is alt
        use_shift = (shift_state & 1) != 0
        
        press_key(vk_code, shift=use_shift)
        
        # Realistic typing speed: 50-150ms per character
        time.sleep(random.uniform(0.05, 0.15))

def run_auto_record():
    print("=== AUTOMATIC CLI RECORDING ===")
    print("The demo will start in 5 seconds.")
    print("IMPORTANT: Switch focus to the terminal window where you want the command typed.")
    
    for i in range(5, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1)
    
    # 1. Start OBS Recording
    start_recording()
    time.sleep(2) # Wait for OBS to stabilize
    
    # 2. Type the command
    command = 'python gws_cli.py --task "Search drive for Python files"'
    print(f"Typing: {command}")
    type_string_realistic(command)
    
    # 3. Press Enter
    time.sleep(0.5)
    press_key(VK_RETURN)
    
    # 4. Wait for command to finish (estimate)
    print("Waiting for CLI execution to complete...")
    time.sleep(15) 
    
    # 5. Stop OBS Recording
    stop_recording()
    print("Recording finished.")

def run():
    """Alias for run_auto_record to provide a consistent entry point."""
    run_auto_record()

if __name__ == "__main__":
    if sys.platform != "win32":
        print("This script is designed for Windows (uses ctypes.windll.user32).")
        sys.exit(1)
        
    run_auto_record()
