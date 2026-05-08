import subprocess
import sys
import threading
import time

def print_dots():
    while True:
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(10)

def main():
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
