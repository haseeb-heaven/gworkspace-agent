import ctypes
import time


def press_key(key_code):
    ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)


def type_string(text):
    for char in text:
        # Simple hack for lowercase and common chars in terminal
        vk = ctypes.windll.user32.VkKeyScanW(ord(char)) & 0xFF
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.05)


def start_obs_recording():
    # Trigger OBS Start Hotkey (Ctrl + F12)
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
    ctypes.windll.user32.keybd_event(0x7B, 0, 0, 0)  # F12
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(0x7B, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)


def stop_obs_recording():
    # Trigger OBS Stop Hotkey (Ctrl + F11)
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
    ctypes.windll.user32.keybd_event(0x7A, 0, 0, 0)  # F11
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(0x7A, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)


def run_cli_demo():
    print("DEMO STARTING IN 5 SECONDS...")
    print("Switch to your terminal window NOW!")
    time.sleep(5)

    start_obs_recording()
    time.sleep(1)

    type_string('python gws_cli.py --task "List my drive files"')
    press_key(0x0D)  # Enter

    # Wait for execution
    time.sleep(8)

    stop_obs_recording()
    print("CLI Demo Recorded.")


if __name__ == "__main__":
    run_cli_demo()
