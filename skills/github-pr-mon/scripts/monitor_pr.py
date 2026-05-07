import time
import argparse
import subprocess  # nosec B404 — subprocess is used safely with controlled commands
import datetime

def run_review(pr_number, repo_name):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Triggering Greptile review for PR #{pr_number} in {repo_name}...")

    # Construct the gemini command
    # Use --yolo to automatically approve the trigger_code_review tool call
    prompt = f"Use the Greptile MCP to review PR #{pr_number} in repo {repo_name} and post findings as a comment. Focus on comprehensive issues."
    cmd = ["gemini", "-p", prompt, "--yolo"]

    try:
        # We use shell=True on Windows if 'gemini' is a batch file/alias,
        # but subprocess.run with a list is generally safer.
        # However, 'gemini' might not be in the PATH as an executable but a script.
        # I'll stick to the provided cmd list.
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # nosec B603 — using list argument, not shell=True
        print(f"[{timestamp}] Review finished successfully.")
        # print(result.stdout) # Optional: too much output?
    except subprocess.CalledProcessError as e:
        print(f"[{timestamp}] Error triggering review: {e.stderr}")
    except FileNotFoundError:
        print(f"[{timestamp}] Error: 'gemini' command not found. Ensure it is in your PATH.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, default=108)
    parser.add_argument("--repo", default="haseeb-heaven/gworkspace-agent")
    parser.add_argument("--interval", type=int, default=300) # 5 minutes
    args = parser.parse_args()

    while True:
        run_review(args.pr, args.repo)
        print(f"Waiting {args.interval} seconds for next check...")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
