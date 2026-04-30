#!/usr/bin/env python3
"""Generate review-guard notification body and write to output file."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-num", required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--comments", required=False)
    parser.add_argument("--comments-file", help="File containing comments payload", required=False)
    parser.add_argument("--issue-num", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    comments = args.comments
    if args.comments_file:
        with open(args.comments_file, "r") as cf:
            comments = cf.read()

    if not comments:
        comments = ""

    if args.issue_num:
        body = (
            f"## \u26a0\ufe0f Merge Blocked on PR #{args.pr_num} "
            f"\u2014 @google-labs-jules please address review comments\n\n"
            f"There are **unresolved review comments** on this PR that must be addressed "
            f"before it can be merged.\n\n"
            f"**PR:** {args.pr_url}\n"
            f"**Head Branch:** `{args.head_ref}`\n"
            f"**Target Branch:** `{args.base_ref}`\n\n"
            f"---\n"
            f"## Unresolved Comments\n\n"
            f"{comments}\n\n"
            f"---\n"
            f"**@google-labs-jules instructions:**\n"
            f"1. Read each unresolved comment carefully\n"
            f"2. Fix the code exactly as suggested by the reviewer\n"
            f"3. Push fix to branch: `{args.head_ref}`\n"
            f"4. Do NOT resolve threads manually "
            f"\u2014 CI will re-check after your push\n"
        )
    else:
        body = (
            f"## \u26a0\ufe0f Merge Blocked \u2014 Unresolved Review Comments\n\n"
            f"@google-labs-jules \u2014 please address all unresolved review comments "
            f"before this PR can be merged.\n\n"
            f"**Head Branch:** `{args.head_ref}`\n"
            f"**Target Branch:** `{args.base_ref}`\n\n"
            f"## Unresolved Comments\n"
            f"{comments}\n"
        )

    with open(args.out, "w") as f:
        f.write(body)


if __name__ == "__main__":
    main()
