#!/usr/bin/env python3
"""Format unresolved review thread comments from a GraphQL response JSON file."""
import sys
import json


def main():
    if len(sys.argv) < 2:
        print("Usage: format_comments.py <response.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    lines = []
    for t in threads:
        if not t["isResolved"] and not t["isOutdated"]:
            c = t["comments"]["nodes"][0] if t["comments"]["nodes"] else {}
            author = c.get("author", {}).get("login", "unknown")
            body = c.get("body", "")[:200]
            path = t.get("path", "unknown file")
            line = t.get("line", "?")
            url = c.get("url", "")
            lines.append(
                f"- **{path}:{line}** by @{author}: {body}\n  {url}"
            )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
