import re
import sys

FORBIDDEN_PATTERNS = [
    r"None",
    r"null",
    r"___UNRESOLVED_PLACEHOLDER___",
    r"\$last_export_file_content",
    r"\$gmail_message_body",
    r"\{task-\d+\}",
    r"\{[a-zA-Z0-9_\-\.\[\]]+\}"
]

def triple_check(content):
    issues = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, str(content), re.IGNORECASE):
            issues.append(f"Found forbidden pattern: {pattern}")

    if not content or str(content).strip() == "":
        issues.append("Content is empty or whitespace.")

    return issues

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Read from file or stdin
        try:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                data = f.read()
        except:
            data = " ".join(sys.argv[1:])
    else:
        data = sys.stdin.read()

    results = triple_check(data)
    if results:
        print("❌ TRIPLE CHECK FAILED:")
        for issue in results:
            print(f"- {issue}")
        sys.exit(1)
    else:
        print("✅ TRIPLE CHECK PASSED: Data is valid and resolved.")
        sys.exit(0)
