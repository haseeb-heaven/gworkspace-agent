"""Browser-based GUI using Gradio."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import tempfile
from dataclasses import dataclass

import gradio as gr
from google_auth_oauthlib.flow import Flow

from .agent_system import WorkspaceAgentSystem
from .config import AppConfig
from .execution import PlanExecutor
from .gws_runner import GWSRunner
from .logging_utils import setup_logging
from .output_formatter import HumanReadableFormatter
from .planner import CommandPlanner

# Google Workspace API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier."""
    # Generate a random 32-byte string and base64url encode it
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    return code_verifier


def generate_code_challenge(code_verifier: str) -> str:
    """Generate a PKCE code challenge from the code verifier."""
    # SHA256 hash the code verifier and base64url encode it
    challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
    return code_challenge


@dataclass(slots=True)
class GradioAssistant:
    planner: CommandPlanner
    agent_system: WorkspaceAgentSystem
    executor: PlanExecutor
    formatter: HumanReadableFormatter
    logger: logging.Logger
    credentials_file: str | None = None

    def run_request(self, user_text: str) -> tuple[str, str]:
        text = (user_text or "").strip()
        if not text:
            return "Enter a request to continue.", ""

        from .langgraph_workflow import run_workflow

        # Set credentials environment variable for this request
        if self.credentials_file:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_file
        elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

        output = run_workflow(
            text, config=AppConfig.from_env(), system=self.agent_system, executor=self.executor, logger=self.logger
        )
        return output, "Plan tracking handled by LangGraph workflow."


def handle_credentials_upload(file_path: str | None) -> tuple[str, str, str]:
    """Handle credentials.json upload and generate OAuth URL."""
    if file_path is None:
        return "", "No file uploaded", "🔴 Not authenticated"

    try:
        with open(file_path, "r") as f:
            credentials_info = json.load(f)

        # Debug: print the structure
        print(f"DEBUG: Credentials keys: {list(credentials_info.keys())}")
        print(f"DEBUG: Credentials type: {credentials_info.get('type', 'N/A')}")

        # Check if it's a service account (not supported for OAuth flow)
        if credentials_info.get("type") == "service_account":
            return "", "Service account keys are not supported for OAuth flow. Please use an OAuth 2.0 Client ID from Google Cloud Console (Desktop app or Web application type).", "🔴 Not authenticated"

        # Validate credentials structure
        if "installed" in credentials_info:
            client_config = credentials_info["installed"]
            client_type = "installed"
            print("DEBUG: Using 'installed' config")
        elif "web" in credentials_info:
            client_config = credentials_info["web"]
            client_type = "web"
            print("DEBUG: Using 'web' config")
        else:
            # Try using the entire file as client config
            client_config = credentials_info
            client_type = None
            print("DEBUG: Using entire file as client config")

        print(f"DEBUG: Client config keys: {list(client_config.keys())}")
        print(f"DEBUG: Has client_id: {'client_id' in client_config}")
        print(f"DEBUG: Has client_secret: {'client_secret' in client_config}")

        if "client_id" not in client_config or "client_secret" not in client_config:
            return "", f"Invalid credentials.json format. Must contain 'client_id' and 'client_secret'. Found keys: {list(credentials_info.keys())}. Please download OAuth 2.0 Client ID credentials from Google Cloud Console.", "🔴 Not authenticated"

        # Construct the proper client secrets structure for Flow
        if client_type:
            client_secrets = {client_type: client_config}
        else:
            # If no type specified, assume it's already in the right format
            client_secrets = client_config

        print(f"DEBUG: Client secrets structure: {list(client_secrets.keys())}")

        # Create OAuth flow with out-of-band redirect
        flow = Flow.from_client_config(
            client_secrets, SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
        # Generate PKCE code verifier and challenge
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        auth_url, _ = flow.authorization_url(prompt="consent", code_challenge=code_challenge)

        # Store client_config, client_type, and code_verifier for later use
        return json.dumps({"client_config": client_config, "client_type": client_type, "code_verifier": code_verifier}), auth_url, "🟡 Waiting for auth code"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "", f"Error processing credentials: {str(e)}", "🔴 Not authenticated"


def regenerate_auth_url(client_config_json: str) -> tuple[str, str]:
    """Regenerate OAuth URL from stored client config."""
    if not client_config_json:
        return "", ""

    try:
        data = json.loads(client_config_json)
        client_config = data["client_config"]
        client_type = data.get("client_type")

        # Construct the proper client secrets structure for Flow
        if client_type:
            client_secrets = {client_type: client_config}
        else:
            client_secrets = client_config

        flow = Flow.from_client_config(
            client_secrets, SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
        # Generate new code_verifier and code_challenge for PKCE
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        auth_url, _ = flow.authorization_url(prompt="consent", code_challenge=code_challenge)

        # Update stored data with new code_verifier
        data["code_verifier"] = code_verifier
        return auth_url, json.dumps(data)

    except Exception as e:
        return "", f"Error regenerating URL: {str(e)}"


def handle_auth_code(client_config_json: str, auth_code: str) -> tuple[str, str]:
    """Exchange authorization code for credentials and return temp file path."""
    if not client_config_json or not auth_code:
        return "", "Missing client config or auth code"

    try:
        data = json.loads(client_config_json)
        client_config = data["client_config"]
        client_type = data.get("client_type")
        code_verifier = data.get("code_verifier")

        # Create OAuth flow - reconstruct the proper structure
        if client_type:
            client_secrets = {client_type: client_config}
        else:
            client_secrets = client_config

        flow = Flow.from_client_config(
            client_secrets, SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )

        # Set code_verifier for PKCE
        if code_verifier:
            flow.code_verifier = code_verifier

        # Exchange code for credentials
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials

        # Create temporary file for credentials
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="gws_credentials_")
        with os.fdopen(temp_fd, "w") as f:
            creds_dict = {
                "type": "authorized_user",
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
            }
            json.dump(creds_dict, f)

        return temp_path, "🟢 Authenticated — ready to use"

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "invalid_grant" in error_msg.lower():
            error_msg = "Authorization code expired or already used. Please generate a new auth URL and try again."
        return "", f"Error exchanging auth code: {error_msg}"


def cleanup_credentials(credentials_file: str | None) -> None:
    """Clean up temporary credentials file."""
    if credentials_file and os.path.exists(credentials_file):
        try:
            os.remove(credentials_file)
        except Exception:
            pass


def create_interface() -> gr.Blocks:
    config = AppConfig.from_env()
    logger = setup_logging(config)

    # In Cloud Run / containerised environments setup_complete may be False
    # because there is no interactive wizard.  We log a warning but continue
    # so the UI can still start up.
    if not config.setup_complete:
        logger.warning(
            "setup_complete is False (no .env or gws binary found via wizard). "
            "Continuing anyway – environment variables should supply all config."
        )

    runner = GWSRunner(config.gws_binary_path, logger=logger, config=config)
    if not runner.validate_binary():
        logger.warning(
            f"gws binary not found at {config.gws_binary_path}. GWS commands will fail, but the UI will still start."
        )

    planner = CommandPlanner()
    assistant = GradioAssistant(
        planner=planner,
        agent_system=WorkspaceAgentSystem(config=config, logger=logger),
        executor=PlanExecutor(planner=planner, runner=runner, logger=logger, config=config),
        formatter=HumanReadableFormatter(),
        logger=logger,
    )

    def update_assistant_credentials(credentials_file: str | None) -> None:
        """Update assistant with new credentials file."""
        assistant.credentials_file = credentials_file

    def run_request_with_auth_check(user_text: str, credentials_file: str | None) -> tuple[str, str]:
        """Run request only if authenticated."""
        if not credentials_file:
            return "Please authenticate with your Google account first.", ""
        assistant.credentials_file = credentials_file
        return assistant.run_request(user_text)

    with gr.Blocks(title="Google Workspace Assistant") as demo:
        gr.Markdown("# Google Workspace Assistant")

        # Authentication section
        with gr.Accordion("🔐 Google Authentication", open=True):
            gr.Markdown("Upload your Google Cloud `credentials.json` file to authenticate with your own Google account.")

            with gr.Row():
                credentials_upload = gr.File(
                    label="Upload credentials.json",
                    file_types=[".json"],
                    type="filepath"
                )

            auth_status = gr.Textbox(
                label="Authentication Status",
                value="🔴 Not authenticated",
                interactive=False
            )

            auth_url_output = gr.Textbox(
                label="Authorization URL",
                placeholder="Upload credentials.json to generate authorization URL",
                interactive=False,
                lines=2
            )

            with gr.Row():
                auth_code_input = gr.Textbox(
                    label="Paste Authorization Code",
                    placeholder="Paste the code from Google after signing in",
                    visible=False
                )
                submit_auth_button = gr.Button("Authenticate", visible=False)
                regenerate_url_button = gr.Button("Generate New Auth URL", visible=False)

            auth_message = gr.Textbox(
                label="Message",
                value="",
                interactive=False,
                visible=False
            )

        gr.Markdown("---")
        gr.Markdown("Describe your Google Workspace task in natural language.")

        with gr.Row():
            request = gr.Textbox(
                label="Request",
                lines=4,
                placeholder="Example: List recent Gmail messages and show details",
            )
        with gr.Row():
            run_button = gr.Button("Run")
            clear_button = gr.Button("Clear")
        output = gr.Textbox(label="Result", lines=18)
        plan_preview = gr.Textbox(label="Planned Tasks", lines=8)

        # Session state for storing client config and credentials file
        client_config_state = gr.State(value="")
        credentials_file_state = gr.State(value=None)

        # Event handlers
        def on_credentials_upload(file):
            client_config, auth_url, status = handle_credentials_upload(file)
            if client_config:
                return (
                    client_config,
                    auth_url,
                    status,
                    auth_url,
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(value="", visible=True),
                    ""
                )
            else:
                return (
                    "",
                    "",
                    status,
                    auth_url,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(value=auth_url, visible=True),
                    auth_url
                )

        def on_regenerate_url(client_config):
            auth_url, updated_config = regenerate_auth_url(client_config)
            return auth_url, updated_config

        def on_auth_submit(client_config, auth_code):
            creds_file, status = handle_auth_code(client_config, auth_code)
            if creds_file:
                update_assistant_credentials(creds_file)
                return (
                    creds_file,
                    status,
                    gr.update(value="", visible=False),
                    gr.update(visible=False),
                    gr.update(value="Authentication successful! You can now use the assistant.", visible=True)
                )
            else:
                return (
                    None,
                    "🔴 Authentication failed",
                    gr.update(value=auth_code, visible=True),
                    gr.update(visible=True),
                    gr.update(value=status, visible=True)
                )

        def on_session_end(credentials_file):
            cleanup_credentials(credentials_file)
            return None

        credentials_upload.upload(
            fn=on_credentials_upload,
            inputs=[credentials_upload],
            outputs=[
                client_config_state,
                auth_url_output,
                auth_status,
                auth_url_output,
                auth_code_input,
                submit_auth_button,
                regenerate_url_button,
                auth_message,
                auth_message
            ]
        )

        regenerate_url_button.click(
            fn=on_regenerate_url,
            inputs=[client_config_state],
            outputs=[auth_url_output, client_config_state]
        )

        submit_auth_button.click(
            fn=on_auth_submit,
            inputs=[client_config_state, auth_code_input],
            outputs=[
                credentials_file_state,
                auth_status,
                auth_code_input,
                regenerate_url_button,
                auth_message
            ]
        )

        run_button.click(
            fn=run_request_with_auth_check,
            inputs=[request, credentials_file_state],
            outputs=[output, plan_preview]
        )

        request.submit(
            fn=run_request_with_auth_check,
            inputs=[request, credentials_file_state],
            outputs=[output, plan_preview]
        )

        clear_button.click(
            fn=lambda: ("", "", ""),
            outputs=[request, output, plan_preview]
        )

        # Note: Gradio doesn't support reliable session cleanup on page unload
        # Temporary credential files will be cleaned up by OS temp directory cleanup

    return demo


def main(host: str = "0.0.0.0", port: int = int(os.environ.get("PORT", 8080)), share: bool = False) -> None:
    interface = create_interface()
    interface.launch(server_name=host, server_port=port, share=share)
