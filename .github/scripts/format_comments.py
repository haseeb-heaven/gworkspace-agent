#!/usr/bin/env python3
"""Format unresolved review thread comments from a GraphQL response JSON file.

Fixes:
  - No body truncation (was [:200], now full body)
  - Fetch ALL comments per thread (not just first 1)
  - Include outdated threads too (marked clearly so Jules knows)
  - Numbered output so Jules can reference each fix
"""
import json
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: format_comments.py <response.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    lines = []
    idx = 0

    for t in threads:
        # Skip only truly resolved threads — include outdated ones (still need fixing)
        if t["isResolved"]:
            continue

        idx += 1
        path = t.get("path", "unknown file")
        line = t.get("line", "?")
        outdated_tag = " *(outdated — still needs fix)*" if t.get("isOutdated") else ""

        lines.append(f"### Comment {idx} — `{path}` line {line}{outdated_tag}")

        # Emit ALL comments in the thread, not just the first one
        for c in t["comments"]["nodes"]:
            author = c.get("author", {}).get("login", "unknown")
            body   = c.get("body", "")   # NO truncation
            url    = c.get("url", "")
            lines.append(f"**@{author}:** {body}")
            if url:
                lines.append(f"🔗 {url}")

        lines.append("")  # blank line between threads

    if not lines:
        print("No unresolved review threads found.")
        return

    print("\n".join(lines))


if __name__ == "__main__":
    main()
