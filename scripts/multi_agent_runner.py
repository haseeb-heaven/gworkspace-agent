import subprocess
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables in the runner itself
load_dotenv()

# Import the tasks from the original script
sys.path.append(os.getcwd())
try:
    from run_live_scenarios import TASKS
except ImportError:
    TASKS = [] # Fallback if import fails

def python_exe():
    return os.environ.get("PYTHON_EXE") or sys.executable

def send_telegram(message):
    subprocess.run([python_exe(), "gws_cli.py", "--send-telegram", message], env=os.environ.copy())

def verify_data(v_type, identifier):
    # Run verify script and capture output
    result = subprocess.run([python_exe(), "scripts/verify_gws_data.py", v_type, identifier], capture_output=True, text=True, env=os.environ.copy())
    return result.returncode == 0, result.stdout + result.stderr

def run_single_task(index, task):
    max_retries = 3
    
    log_dir = os.path.join("logs", "tasks")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"task_{index}.log")
    
    send_telegram(f"🚀 [Agent {index}] Starting: {task[:60]}...")
    
    for attempt in range(max_retries):
        full_stdout = []
        full_stderr = []
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- Attempt {attempt + 1} at {time.ctime()} ---\n")
            f.flush()
            
            # Use Popen for real-time logging
            process = subprocess.Popen(
                [python_exe(), "-u", "gws_cli.py", "--task", task],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=os.environ.copy(),
                bufsize=1
            )
            
            # Monitor stdout/stderr in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    f.write(line)
                    f.flush()
                    full_stdout.append(line)
            
            _, stderr_remaining = process.communicate()
            if stderr_remaining:
                f.write(stderr_remaining)
                f.flush()
                full_stderr.append(stderr_remaining)
            
        stdout = "".join(full_stdout)
        stderr = "".join(full_stderr)
        success = process.returncode == 0
        
        if "___UNRESOLVED_PLACEHOLDER___" in stdout:
            success = False
            stderr += "\nDetected unresolved placeholders!"

        if success:
            v_type = None
            identifier = None
            
            if "Sheet" in task or "Sheet" in stdout:
                v_type = "sheet"
                if "ID '" in stdout:
                    identifier = stdout.split("ID '")[1].split("'")[0]
                elif "named '" in stdout:
                    identifier = stdout.split("named '")[1].split("'")[0]
            elif "Doc" in task or "Doc" in stdout:
                v_type = "doc"
                if "named '" in stdout:
                    identifier = stdout.split("named '")[1].split("'")[0]
            
            if v_type and identifier:
                v_success, v_log = verify_data(v_type, identifier)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- Verification for {v_type} {identifier} ---\n")
                    f.write(v_log)
                
                if v_success:
                    send_telegram(f"✅ [Agent {index}] SUCCESS & VERIFIED: {task[:50]}")
                    return index, True, stdout
                else:
                    success = False
                    stderr += f"\nVerification Failed:\n{v_log}"
            else:
                send_telegram(f"✅ [Agent {index}] SUCCESS (No verification target found): {task[:50]}")
                return index, True, stdout

        if attempt < max_retries - 1:
            send_telegram(f"⚠️ [Agent {index}] FAILED attempt {attempt + 1}. Retrying in 30s...")
            time.sleep(30)
        else:
            send_telegram(f"❌ [Agent {index}] FINAL FAILURE: {task[:50]}\nError: {stderr[-200:]}")
            return index, False, stderr

def main():
    print(f"Running {len(TASKS)} tasks throttled (max_workers=3, 45s spawn delay)...")
    
    max_workers = 3
    spawn_delay = 45
    
    all_results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, task in enumerate(TASKS):
            futures.append(executor.submit(run_single_task, i, task))
            if i < len(TASKS) - 1:
                print(f"Waiting {spawn_delay}s before spawning Agent {i+1}...")
                time.sleep(spawn_delay)
                
        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)
                
    success_count = sum(1 for _, success, _ in all_results if success)
    print(f"\nFinal Results: {success_count}/{len(TASKS)} passed.")
    send_telegram(f"🏁 ALL TASKS COMPLETED. Results: {success_count}/{len(TASKS)} passed.")

if __name__ == "__main__":
    main()
