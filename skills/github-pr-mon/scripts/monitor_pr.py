import time
import argparse
import subprocess
import json
import os

def post_comment(pr_url, body):
    subprocess.run(["gh", "pr", "comment", pr_url, "--body", body], check=True)

def run_review(pr_url):
    # Placeholder for Greptile trigger
    print(f"Reviewing {pr_url}...")
    return "Review complete. No new issues found."

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", required=True)
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    while True:
        report = run_review(args.pr)
        # Logic to only post if content changed would go here
        print(report)
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
