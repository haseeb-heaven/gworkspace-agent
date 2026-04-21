import ctypes
import time
import sys
import os
from pathlib import Path

# Add the project root to sys.path to allow imports from scripts or src
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from scripts.obs_controller import start_recording, stop_recording
except ImportError:
    # Fallback if scripts is not a package
    sys.path.append(str(PROJECT_ROOT / "scripts"))
    from obs_controller import start_recording, stop_recording

# Windows API Constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_A = 0x41
VK_BACK = 0x08
VK_SHIFT = 0x10

# Virtual-Key Codes for basic alphanumeric characters
VK_CODES = {
    ' ': 0x20,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
    'z': 0x5A,
}

def click(x, y):
    """Simulate a mouse click at (x, y)."""
    print(f"Clicking at ({x}, {y})")
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def press_key(vk_code):
    """Simulate a key press and release."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)

def type_string(s):
    """Simulate typing a string."""
    for char in s.lower():
        if char in VK_CODES:
            press_key(VK_CODES[char])
        elif char == ':':
            # Simplified shift+: handling if needed
            ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 0, 0)
            press_key(0xBA)
            ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 2, 0)
        time.sleep(0.05)

def main():
    """
    Automate GUI interaction and record with OBS.
    Assumes 1920x1080 resolution and GUI centered.
    """
    # Screen Constants
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 1080
    CENTER_X = SCREEN_WIDTH // 2
    CENTER_Y = SCREEN_HEIGHT // 2

    # UI Offsets (based on 980x700 GUI centered on screen)
    # 1. Input Box (centered horizontally, upper part of window)
    INPUT_X = CENTER_X
    INPUT_Y = CENTER_Y - 242

    # 2. Analyze Button (Left side of the controls frame)
    ANALYZE_X = CENTER_X - 352
    ANALYZE_Y = CENTER_Y - 161

    # 3. Execute Button (Right side of the controls frame)
    EXECUTE_X = CENTER_X + 352
    EXECUTE_Y = CENTER_Y - 161

    print("--- GUI Automation & Recording ---")
    print("Please ensure the GUI is open and centered on a 1920x1080 screen.")
    print("Automation will start in 5 seconds. Switch to the GUI window now!")
    time.sleep(5)

    try:
        start_recording()
        time.sleep(2)

        # Step 1: Click and clear input box
        click(INPUT_X, INPUT_Y)
        time.sleep(0.5)
        # Select All (Ctrl+A)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        press_key(VK_A)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)
        # Clear (Backspace)
        press_key(VK_BACK)
        time.sleep(0.5)

        # Step 2: Type request
        request = "list latest drive files"
        print(f"Typing: '{request}'")
        type_string(request)
        time.sleep(1)

        # Step 3: Click Analyze
        print("Analyzing request...")
        click(ANALYZE_X, ANALYZE_Y)
        time.sleep(4)  # Wait for analysis and planner to respond

        # Step 4: Click Execute
        print("Executing command...")
        click(EXECUTE_X, EXECUTE_Y)
        time.sleep(8)  # Wait for execution to complete and show in output

        print("Automation finished.")
    except KeyboardInterrupt:
        print("\nAborted by user.")
    finally:
        stop_recording()
        print("Recording stopped.")

def run():
    """Alias for main to provide a consistent entry point."""
    main()

if __name__ == "__main__":
    main()
