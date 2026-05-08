import re
import time
import argparse
import subprocess  # nosec B404 — subprocess is used safely with controlled commands
import datetime

_REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def run_review(pr_number: int, repo_name: str) -> None:
    """Trigger a Greptile review for the given PR via the gemini CLI and print the result.

    Args:
        pr_number: The pull request number to review.
        repo_name: The repository name in 'owner/repo' format.

    Raises:
        ValueError: If repo_name does not match the expected owner/repo pattern.
    """
    # Validate repo_name format to prevent prompt injection
    if not _REPO_RE.fullmatch(repo_name):
        raise ValueError(f"Invalid repo_name format: {repo_name!r}")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Triggering Greptile review for PR #{pr_number} in {repo_name}...")

    # Construct the gemini command
    # Use --yolo to automatically approve the trigger_code_review tool call
    # nosec B603 — using list argument, not shell=True; repo_name validated by regex
    # nosec — accepted risk: --yolo auto-approves tool calls; repo_name is validated
    prompt = f"Use the Greptile MCP to review PR #{pr_number} in repo {repo_name} and post findings as a comment. Focus on comprehensive issues."
    cmd = ["gemini", "-p", prompt, "--yolo"]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        print(f"[{timestamp}] Review finished successfully.")
    except subprocess.TimeoutExpired:
        print(f"[{timestamp}] Review timed out after 120 seconds; skipping this cycle.")
    except subprocess.CalledProcessError as e:
        print(f"[{timestamp}] Error triggering review: {e.stderr}")
    except FileNotFoundError:
        print(f"[{timestamp}] Error: 'gemini' command not found. Ensure it is in your PATH.")

def main() -> None:
    """Parse CLI arguments and run the review loop indefinitely."""
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
