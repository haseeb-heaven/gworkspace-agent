import json
import os
import subprocess
import sys


def run_gws_command(task):
    """Run a gws_cli task and return the output."""
    python_exe = os.environ.get("PYTHON_EXE") or sys.executable
    result = subprocess.run([python_exe, "gws_cli.py", "--task", task], capture_output=True, text=True, encoding="utf-8")
    return result.stdout, result.stderr

def check_content(content, source_name):
    """Check content for common invalid patterns."""
    invalid_patterns = [
        "___UNRESOLVED_PLACEHOLDER___",
        "{{", "}}",  # common template markers
        "None", "null", "NaN", "N/A", "empty",
        "unknown", "undefined"
    ]

    issues = []
    if not content or not content.strip():
        issues.append(f"[{source_name}] Content is empty or whitespace.")
        return issues

    for pattern in invalid_patterns:
        if pattern.lower() in content.lower():
            # Check if it's a false positive (e.g., the word 'none' in a sentence)
            # For strictness, we'll flag it anyway in this 'high level verification'
            issues.append(f"[{source_name}] Found suspicious pattern: '{pattern}'")

    return issues

def verify_sheet(sheet_id_or_name):
    print(f"Verifying Sheet: {sheet_id_or_name}")
    stdout, stderr = run_gws_command(f"Read Google Sheet '{sheet_id_or_name}' and return all data as JSON")
    try:
        # Assuming the agent returns something like "Data: [...]"
        if "Data:" in stdout:
            data_str = stdout.split("Data:")[1].strip()
            data = json.loads(data_str)
            content = str(data)
        else:
            content = stdout
    except Exception:
        content = stdout

    return check_content(content, f"Sheet:{sheet_id_or_name}")

def verify_doc(doc_name):
    print(f"Verifying Doc: {doc_name}")
    stdout, stderr = run_gws_command(f"Read Google Doc '{doc_name}' and return content")
    return check_content(stdout, f"Doc:{doc_name}")

def verify_gmail(query):
    print(f"Verifying Gmail search: {query}")
    stdout, stderr = run_gws_command(f"Search Gmail for '{query}' and return the latest message body")
    return check_content(stdout, f"Gmail:{query}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python verify_gws_data.py <type> <identifier>")
        print("Types: sheet, doc, gmail")
        sys.exit(1)

    v_type = sys.argv[1].lower()
    identifier = sys.argv[2]

    all_issues = []
    # Triple check logic: we run the verification 3 times (or check 3 different ways if possible)
    # Here we'll just run it once but very thoroughly.
    for i in range(3):
        print(f"Pass {i+1}/3...")
        if v_type == "sheet":
            issues = verify_sheet(identifier)
        elif v_type == "doc":
            issues = verify_doc(identifier)
        elif v_type == "gmail":
            issues = verify_gmail(identifier)
        else:
            print(f"Unknown type: {v_type}")
            sys.exit(1)

        all_issues.extend(issues)

    # Deduplicate issues
    all_issues = list(set(all_issues))

    if all_issues:
        print("\n--- VERIFICATION FAILED ---")
        for issue in all_issues:
            print(f"ERROR: {issue}")
        sys.exit(1)
    else:
        print("\n--- VERIFICATION PASSED ---")
        sys.exit(0)

if __name__ == "__main__":
    main()
