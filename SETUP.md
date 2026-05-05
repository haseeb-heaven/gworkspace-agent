# Setup Guide: Google Workspace Agent

This guide provides step-by-step instructions to set up the Google Workspace Agent, including Google Cloud credentials and the required CLI tools.

---

## 📋 Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Google Cloud Account** (Free tier works)
- **OpenRouter API Key** (Required for LLM planning)

---

## 🛠️ Step 1: Install Python Dependencies

1. **Clone the repository:**
   ```bash
   git clone https://github.com/haseeb-heaven/gworkspace-agent.git
   cd gworkspace-agent
   ```

2. **Create a virtual environment:**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the package:**
   ```bash
   pip install -e .
   ```

---

## 📂 Step 2: Install Google Workspace CLI (`gws`)

The agent relies on the [Google Workspace CLI](https://github.com/googleworkspace/cli) to interact with Google Services.

### Download the Binary
1. Go to the [GitHub Releases page](https://github.com/googleworkspace/cli/releases).
2. Download the version for your operating system:
   - **Windows:** `google-workspace-cli-x86_64-pc-windows-msvc.zip` (contains `gws.exe`)
   - **macOS:** `google-workspace-cli-x86_64-apple-darwin.tar.gz`
   - **Linux:** `google-workspace-cli-x86_64-unknown-linux-musl.tar.gz`
3. Extract the file and move the `gws` (or `gws.exe`) binary to a folder on your computer.
4. **Add to PATH:** Ensure the folder containing the binary is in your system's `PATH` environment variable.
   - *Verification:* Open a new terminal and type `gws --version`.

---

## ☁️ Step 3: Google Cloud & Credentials Setup

You need a Google Cloud Project to authorize the agent. You can do this automatically or manually.

### Option A: Automated Setup (Recommended)
If you have the [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) installed:
1. Run:
   ```bash
   gws auth setup
   ```
2. Follow the prompts to create a project and enable APIs automatically.

### Option B: Manual Setup (via Browser)
1. **Create a Project:** Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. **Enable APIs:** Enable the following APIs in the "Library" section. Refer to the table below for the complete list of supported services and their enable URLs.

| API | GWS Commands | Enable URL |
|-----|--------------|------------|
| Gmail API | list_messages, get_message, send_message, trash_message, delete_message | https://console.cloud.google.com/apis/library/gmail.googleapis.com |
| Google Drive API | list_files, create_folder, upload_file, get_file, create_file, export_file, delete_file, move_to_trash, update_file_metadata, move_file, copy_file | https://console.cloud.google.com/apis/library/drive.googleapis.com |
| Google Sheets API | create_spreadsheet, get_spreadsheet, get_values, append_values, delete_spreadsheet, clear_values | https://console.cloud.google.com/apis/library/sheets.googleapis.com |
| Google Docs API | create_document, get_document, batch_update | https://console.cloud.google.com/apis/library/docs.googleapis.com |
| Google Calendar API | list_events, create_event, get_event, delete_event, update_event | https://console.cloud.google.com/apis/library/calendar-json.googleapis.com |
| Google Tasks API | list_tasklists, list_tasks, create_task, delete_task, update_task | https://console.cloud.google.com/apis/library/tasks.googleapis.com |
| Google Slides API | create_presentation, get_presentation | https://console.cloud.google.com/apis/library/slides.googleapis.com |
| Google Contacts API | list_contacts, list_directory_people, get_person | https://console.cloud.google.com/apis/library/people.googleapis.com |
| Google Chat API | list_spaces, send_message, list_messages, get_message | https://console.cloud.google.com/apis/library/chat.googleapis.com |
| Google Meet API | list_conferences, get_conference, create_meeting | https://console.cloud.google.com/apis-library/meet.googleapis.com |
| Google Keep API | list_notes, create_note, get_note, delete_note | https://console.cloud.google.com/apis/library/keep.googleapis.com |
| Google Admin SDK Reports API | list_activities, log_activity | https://console.cloud.google.com/apis/library/admin.googleapis.com |
3. **Configure OAuth Consent Screen:**
   - Go to **APIs & Services > OAuth consent screen**.
   - Select **External**.
   - Add your email as a **Test User** (Mandatory).
4. **Create Credentials:**
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials > OAuth client ID**.
   - Select **Desktop app**.
   - Download the JSON file and rename it to `client_secret.json`.
5. **Place the Secret:**
   - **Windows:** Move it to `C:\Users\<YourUser>\.config\gws\client_secret.json`
   - **macOS/Linux:** Move it to `~/.config/gws/client_secret.json`

---

## 🔐 Step 4: Authentication

Once the credentials are in place, run:
```bash
gws auth login
```
This will open your browser. Log in with your Google account and grant the requested permissions.

---

## ⚙️ Step 5: Agent Configuration

1. **Initialize the Agent:**
   ```bash
   python gws_cli.py --setup
   ```
2. The wizard will ask for:
   - Path to the `gws` binary (if not in PATH).
   - Your **OpenRouter API Key**.
   - Optional keys (Tavily, E2B).
3. The configuration will be saved to a `.env` file.

---

## ✅ Step 6: Verify Installation

Run a simple task to verify everything is working:
```bash
python gws_cli.py --task "List my 5 most recent Drive files"
```

---

## ❓ Troubleshooting

- **gws not found:** Ensure `gws` is in your PATH or specify the full path during `python gws_cli.py --setup`.
- **Authentication errors:** Ensure you added your email as a **Test User** in the Google Cloud OAuth consent screen.
- **Binary downloads:** Always get the latest binary from the [official releases](https://github.com/googleworkspace/cli/releases).
