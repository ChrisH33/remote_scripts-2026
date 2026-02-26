"""
UploadToDrive.py
----------------
Watches a network directory for CSV/PDF files, uploads them to a
Google Drive folder, and moves them to a "Processed" subfolder.
Sends a Slack summary after each batch.
"""

# stdlib
import os
import sys
import time
from pathlib import Path
from typing import List

# third-party
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# internal
from config import load_var, logger
from file_mover import move_to_processed, upload_file_to_google

# Shared project utilities
project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))

# BUG FIX: UniFunction no longer exists — prod_mode() lives in utils.config
from utils.config import prod_mode
from utils.slack_wrapper import SlackClientWrapper


# =============================================================================
# Google Drive auth
# =============================================================================

def build_drive_service(config, scopes):
    """
    Authenticate with Google Drive using stored credentials, refreshing or
    re-running the OAuth flow as needed.  Returns a Drive API service object.
    """
    creds = None

    # Load cached credentials if they exist
    if os.path.exists(config.google_token):
        creds = Credentials.from_authorized_user_file(config.google_token, scopes)

    # Refresh or re-authenticate if credentials are missing or expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.credentials, scopes)
            creds = flow.run_local_server(port=0)

        # Persist the (possibly refreshed) token so we don't re-auth every run
        with open(config.google_token, "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# =============================================================================
# Retry helper
# =============================================================================

def retry(func, retries: int = 3, delay: float = 1.0, *args, **kwargs):
    """
    Call `func(*args, **kwargs)` up to `retries` times, waiting `delay`
    seconds between attempts.

    Returns the function's return value on success, or False after all
    retries are exhausted.

    Note: retries and delay must be passed as keyword arguments because
    *args sits between them and the caller's positional arguments.
    """
    for attempt in range(1, retries + 1):
        try:
            result = func(*args, **kwargs)
            if result:
                return result   # BUG FIX: return the actual result, not just True
            logger.warning(f"Attempt {attempt}/{retries} failed for {func.__name__}: returned falsy")
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{retries} failed for {func.__name__}: {e}")
        if attempt < retries:
            time.sleep(delay)
    logger.error(f"{func.__name__} failed after {retries} attempts")
    return False


# =============================================================================
# Initialise config, Slack, Drive
# =============================================================================

config        = load_var()
slack_wrapper = SlackClientWrapper(bot_token=config.slack_bot_token)
service       = build_drive_service(config, config.scopes)

# =============================================================================
# Main monitoring loop
# =============================================================================

while True:
    # BUG FIX: sleep was at the TOP of the loop, adding unnecessary delay on
    # the very first iteration, and causing a *double* sleep when no files were
    # found (once inside the `if not files` branch and again at the top of the
    # next iteration).  Sleep belongs at the BOTTOM, after each cycle.

    # ── Scan network directory for uploadable files ───────────────────────
    try:
        files = [
            f for f in os.listdir(config.network_dir)
            if f.lower().endswith((".csv", ".pdf"))
        ]
    except Exception:
        logger.exception("Error accessing network directory")
        time.sleep(5)
        continue

    # ── Process each file ─────────────────────────────────────────────────
    uploaded_files: List[str] = []

    for file_name in files:
        full_path = os.path.join(config.network_dir, file_name)

        # Attempt upload; if it succeeds, attempt the move to Processed
        if retry(upload_file_to_google, retries=3, delay=2,
                 file_path=full_path, FOLDER_ID=config.mave_folder_id, service=service):

            if retry(move_to_processed, retries=3, delay=1,
                     file_path=full_path, dir=config.processed_network_dir):
                uploaded_files.append(file_name)
            else:
                logger.error(f"Upload succeeded but move to Processed failed: {full_path}")
        else:
            logger.error(f"Failed to upload to Google Drive after retries: {full_path}")

    # ── Slack summary ─────────────────────────────────────────────────────
    if uploaded_files:
        message_text = (
            f"Uploaded {len(uploaded_files)} file(s) to Google Drive:\n"
            + "\n".join(uploaded_files)
        )
        slack_wrapper.send_message(channel=config.channel_id, text=message_text)

    # ── Loop control ──────────────────────────────────────────────────────
    if not prod_mode():
        break   # On non-Linux (dev) machines, run exactly one cycle

    time.sleep(config.refresh_rate)