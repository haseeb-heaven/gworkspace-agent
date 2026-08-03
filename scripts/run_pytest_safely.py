import subprocess
import sys
import threading
import time


def print_dots() -> None:
    """Run an infinite loop writing dots to stdout.

    This function writes a dot every 10 seconds to indicate progress and is
    safe for use in a daemon thread.
    """
    while True:
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(10)

def main() -> None:
    """Execute pytest in a subprocess while printing progress dots.

    Starts a background thread for dots, runs pytest redirecting output to
    'pytest_output.log', and exits with the subprocess return code.
    """
    t = threading.Thread(target=print_dots, daemon=True)
    t.start()

    with open("pytest_output.log", "w", encoding="utf-8") as f:
        process = subprocess.Popen(
            [sys.executable, "-m", "pytest", "-m", "manual or live_integration", "-n", "4", "-q", "--tb=short"],
            stdout=f,
            stderr=subprocess.STDOUT
        )
        process.wait()

    print("\nPytest finished with code", process.returncode)
    sys.exit(process.returncode)

if __name__ == "__main__":
    main()
