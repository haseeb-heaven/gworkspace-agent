import ctypes
import time
import sys
import os
import webbrowser
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
        time.sleep(0.05)

def main():
    """
    Open Web GUI, automate interaction, and record with OBS.
    Assumes a 1920x1080 screen resolution.
    """
    url = "http://localhost:7860"
    
    # Approximate coordinates for Gradio Request textbox on a 1920x1080 screen
    # when browser is maximized.
    INPUT_X = 960
    INPUT_Y = 400

    print("--- Web Automation & Recording ---")
    print(f"Target URL: {url}")
    print("Opening browser...")
    webbrowser.open(url)
    
    # Wait for browser to open and Gradio to load
    print("Waiting 10 seconds for page load...")
    time.sleep(10)

    try:
        # Start OBS Recording
        start_recording()
        time.sleep(2)

        # Step 1: Focus the chat input
        click(INPUT_X, INPUT_Y)
        time.sleep(0.5)

        # Step 2: Clear any existing text (Select All + Backspace)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        press_key(VK_A)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)
        press_key(VK_BACK)
        time.sleep(0.5)

        # Step 3: Type the request
        request_text = "list latest drive files"
        print(f"Typing request: '{request_text}'")
        type_string(request_text)
        time.sleep(1)

        # Step 4: Submit the request (Enter key)
        print("Submitting request...")
        press_key(VK_RETURN)

        # Step 5: Wait for processing and display of results
        print("Waiting for results (15 seconds)...")
        time.sleep(15)

        print("Automation sequence complete.")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        # Stop OBS Recording
        stop_recording()
        print("Recording stopped.")

def run():
    """Alias for main to provide a consistent entry point."""
    main()

if __name__ == "__main__":
    main()
