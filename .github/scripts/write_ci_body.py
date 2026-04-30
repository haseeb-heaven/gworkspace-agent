#!/usr/bin/env python3
"""Generate Jules CI failure comment body and write to output file."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["issue", "pr"], required=True)
    parser.add_argument("--pr-num", required=True)
    parser.add_argument("--pr-url", default="")
    parser.add_argument("--head-branch", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--errors-file", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.errors_file) as f:
        errors = f.read()

    if args.type == "issue":
        body = (
            f"## \u274c CI Failed on PR #{args.pr_num} "
            f"\u2014 @google-labs-jules please fix\n\n"
            f"CI pipeline failed. Fix the errors below and push to the same branch.\n\n"
            f"**PR:** {args.pr_url}\n"
            f"**Head Branch:** `{args.head_branch}`\n"
            f"**Target Branch:** `{args.base_branch}`\n"
            f"**Failed Run:** {args.run_url}\n\n"
            f"---\n"
            f"## Errors\n"
            f"{errors}\n"
            f"---\n\n"
            f"**@google-labs-jules instructions:**\n"
            f"1. Fix all failing tests and lint errors listed above\n"
            f"2. Fix source code only \u2014 do NOT modify test logic\n"
            f"3. Push fix to branch: `{args.head_branch}`\n"
            f"4. Do NOT merge \u2014 CI will auto-merge into "
            f"`{args.base_branch}` once all checks pass\n"
        )
    else:
        body = (
            f"## \u274c CI Failed \u2014 @google-labs-jules please fix\n\n"
            f"@google-labs-jules \u2014 CI pipeline failed. "
            f"No linked Issue was found so tagging here directly.\n\n"
            f"**Head Branch:** `{args.head_branch}`\n"
            f"**Target Branch:** `{args.base_branch}`\n"
            f"**Failed Run:** {args.run_url}\n\n"
            f"## Errors\n"
            f"{errors}\n\n"
            f"**Instructions:**\n"
            f"1. Fix all errors above\n"
            f"2. Push fix to branch: `{args.head_branch}`\n"
            f"3. Do NOT merge \u2014 CI will auto-merge into "
            f"`{args.base_branch}` once all checks pass\n"
        )

    with open(args.out, "w") as f:
        f.write(body)


if __name__ == "__main__":
    main()
