import subprocess
import os
import sys
import time

TASKS = [
    "Search Gmail for 'offer letter', extract sender, subject, and date, save to a new Google Sheet named 'Job Offer Letter Sheet', then send me an email with the sheet link and also attach this document",
    "Search Gmail for 'job offer OR hiring', extract all company names and dates, append to a new Google Sheet tab named 'Job Offers', then send a summary email with the sheet link and a data table",
    "Search Gmail for all emails from the default email, extract subject, date, and body, append to a new Google Sheet, then send email with the sheet link",
    "Search Gmail for all emails from the default email extract sender names and email addresses to a new Google Sheet, then send email with the sheet link",
    "Search Gmail for 'Your receipt from X', extract all charge amounts and dates, use code executor to calculate total USD cost and convert to INR, save all data to a new Google Sheet with columns: Date, Amount USD, Amount INR, then send email with subject 'X Premium Expenses' and the sheet link",
    "Search Gmail for 'Your receipt from X' from last month and this month, extract charge amounts, use code executor to convert USD to INR, save to Google Sheet with columns: Month, USD Amount, INR Amount, then send email with subject 'X Premium Subscription Expenses' and the sheet link",
    "Search Gmail for bank statements received this month, extract bank name and total amount due, save to a new Google Sheet with columns: Bank Name, Statement Date, Amount Due, then send email with the sheet link",
    "Search Google Drive for document named 'Shibuz', read its content, then send email with the document content",
    "Search Google Drive for document named 'CcaaS - AI Product', then send email with message: 'Please check this document and give me feedback on this product, thanks'",
    "Find Price of Codex and Claude Code and Gemini CLI and save that to Sheets and then using code interpreter give me the cheapest one and save that to document only single cheapest and send that to email and attach the file and add links"
]

def spawn_subagent(index, task):
    print(f"Spawning agent {index} for task: {task[:50]}...")
    python_exe = os.environ.get("PYTHON_EXE") or sys.executable
    
    full_task = f"""
TASK: {task}
MANDATORY VERIFICATION: 
1. Run the task using gws_cli.py.
2. Use scripts/verify_gws_data.py to TRIPLE-CHECK the results (Sheet, Doc, or Gmail).
3. If verification fails, fix the issue and retry.
4. Send progress updates to Telegram using .agent/skills/telegram-update/scripts/send_message.py.
5. Provide a final verification report in the output.
"""
    
    cmd = [
        python_exe, ".agent/skills/superpowers-workflow/scripts/spawn_subagent.py",
        "--skill", "python-automation",
        "--task", full_task
    ]
    
    # Increase Node.js memory limit for the subagent
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-old-space-size=4096"
    
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

def main():
    # Run in sub-batches of 5 to avoid memory issues
    batch_size = 5
    for i in range(0, len(TASKS), batch_size):
        sub_tasks = TASKS[i:i+batch_size]
        processes = []
        for j, task in enumerate(sub_tasks):
            p = spawn_subagent(i + j, task)
            processes.append(p)
            time.sleep(5) # Space them out more
            
        print(f"Waiting for sub-batch {i//batch_size + 1} to complete...")
        for j, p in enumerate(processes):
            stdout, stderr = p.communicate()
            print(f"Agent {i + j} finished.")
            if p.returncode != 0:
                print(f"Agent {i + j} FAILED with code {p.returncode}")
                print(f"Error: {stderr}")

if __name__ == "__main__":
    main()
