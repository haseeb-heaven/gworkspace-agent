#!/usr/bin/env python3
"""Count unresolved, non-outdated review threads from a GraphQL response JSON file."""
import sys
import json


def main():
    if len(sys.argv) < 2:
        print("Usage: count_unresolved.py <response.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    count = sum(1 for t in threads if not t["isResolved"] and not t["isOutdated"])
    print(count)


if __name__ == "__main__":
    main()
