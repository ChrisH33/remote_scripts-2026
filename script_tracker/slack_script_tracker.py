import psutil
import os

def get_active_scripts(keywords: list[str]) -> set[str]:
    """
    Scan all running processes and return a set of currently executing Python scripts,
    excluding those matching specified keywords.

    Args:
        keywords (list[str]): List of substrings to ignore in command-line arguments.

    Returns:
        set[str]: Set of Python script basenames currently running.
    """
    scripts = set()

    # Iterate over all running processes
    for proc in psutil.process_iter(['cmdline']):
        cmd = proc.info['cmdline']
        try:
            # Skip processes with no command-line info or non-Python executables
            if not cmd or "python" not in os.path.basename(cmd[0]).lower():
                continue

            # Check all arguments passed to the interpreter
            for arg in cmd[1:]:
                arg_lower = arg.lower()

                # Skip if the argument matches any of the ignore keywords
                if any(k in arg_lower for k in keywords):
                    continue

                # Only consider actual Python script files that exist on disk
                if arg_lower.endswith(".py") and os.path.isfile(arg):
                    # Add the script's basename without the .py extension
                    scripts.add(os.path.splitext(os.path.basename(arg))[0])
                    break  # Stop after first valid script in this process

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return scripts

def build_status_bar(blocks, max_blocks, emoji_map):
    padded_blocks = blocks.copy()
    while len(padded_blocks) < max_blocks:
        padded_blocks.insert(0, "grey")
    return "".join([emoji_map.get(status, emoji_map["grey"]) for status in padded_blocks])

def rollover_blocks(status_bar, max_blocks):
    while len(status_bar) > max_blocks:
        status_bar.pop(0)  # remove oldest block
    return status_bar
            
def build_slack_blocks(header, max, emojis):
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{header}",
            "emoji": True
        }})
    
    # Scripts Section
    for script, block_list in script_history.items():
        status_bar = build_status_bar(active_block_state.get(script, block_list), max, emojis)
        blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{script}*\n{status_bar}"
        }})

    # Last update
    last_update = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"last update:\n`{last_update}`"
        }
    })

    return blocks

def update_live_status(scripts, cycle_time):
    """
    Update the active_block_state for scripts currently running.
    Adds:
      - green blocks every CYCLE_TIME while active
      - red blocks when scripts disappear
      - orange blocks when scripts return after a disappearance
    """
    now = datetime.now(timezone.utc)

    # New or active scripts
    for script in scripts:
        if script not in script_history:
            script_history[script] = []
            active_block_state[script] = []
            block_start_time[script] = now

        # Add a green block if enough time (CYCLE_TIME) has passed
        last_time = block_start_time.get(script, now - cycle_time)
        if not active_block_state[script] or (now - last_time) >= cycle_time:
            active_block_state[script].append("green")
            block_start_time[script] = now

    # Scripts that vanished
    for script in script_history.keys():
        if script not in scripts:
            last_status = active_block_state.get(script, [])[-1:]
            if not last_status or last_status[0] != "red":
                active_block_state.setdefault(script, []).append("red")
                block_start_time[script] = now

    # Scripts that returned after vanish
    for script in scripts:
        last_status = active_block_state.get(script, [])[-1:]
        if last_status and last_status[0] == "red":
            active_block_state[script][-1] = "orange"
            block_start_time[script] = now

#stdlib
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# internal
from config import load_var, active_block_state
from message_builder import build_slack_blocks, update_live_status, rollover_blocks
from process_scan import get_active_scripts

# Shared Ubuntu scripts
project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))
import UniFunction
from SlackClientWrapper.slack_client_wrapper.slack_wrapper import SlackClientWrapper

# =================================================================
# Set Config & Slack
# =================================================================

config = load_var()
slack_wrapper = SlackClientWrapper(bot_token=config.slack_bot_token)

# Send started Slack message
blocks = build_slack_blocks(
    config.status_header,
    config.max_blocks,
    config.emoji_map
)
ts = slack_wrapper.send_message(
    channel=config.channel_id,
    text="temp text",
    blocks=blocks
)

# =================================================================
# Main monitoring loop
# =================================================================

while True:
    # 1. Detect active scripts
    currently_active_scripts = get_active_scripts(config.keywords)

    # 2. Update block statuses
    update_live_status(currently_active_scripts, config.cycle_time)
    rollover_blocks(active_block_state, config.max_blocks)

    # 3. Update Slack message
    blocks = build_slack_blocks(
        config.status_header,
        config.max_blocks,
        config.emoji_map
    )
    slack_wrapper.update_message(
        message_ts=ts,
        channel=config.channel_id,
        text="temp text",
        blocks=blocks
    )

    # 4. Break loop (optional)
    if not UniFunction.prod_mode():
        break

    # 5. 'Wait for' timer
    time.sleep(config.refresh_rate)


from datetime import timedelta
from dataclasses import dataclass
from typing import Dict
from dotenv import load_dotenv
import sys
from pathlib import Path
from utils.config import require_env

# -------------------------------------------------
# Variables
# -------------------------------------------------

active_block_state = {}
script_history = {}
block_start_time = {}

# -------------------------------------------------
# Environmental Variables
# -------------------------------------------------

load_dotenv()
SLACK_BOT_TOKEN = require_env("SLACK_BOT_TOKEN")
CHANNEL_ID = require_env("SLACK_CHANNEL_RemoteLog")

# -------------------------------------------------
# Config object
# -------------------------------------------------

@dataclass(frozen=True)
class Config:
    max_blocks: int
    cycle_time: int
    refresh_rate: int
    keywords: list[str]
    status_header: str
    emoji_map: Dict[str, str]
    slack_bot_token: str
    channel_id: str

# -------------------------------------------------
# Public API
# -------------------------------------------------

def load_var() -> Config:
    return Config(
        max_blocks = 15,
        cycle_time = timedelta(minutes=1),
        refresh_rate = 20,
        keywords = ['launcher', 'debugpy', 'pythonw.exe'],
        status_header = "Remote Ubuntu Dashboard :skull:",
        emoji_map = {
            "green": ":large_green_square:",
            "red": ":large_red_square:",
            "orange": ":large_orange_square:",
            "grey": ":black_large_square:",
        },
        slack_bot_token=SLACK_BOT_TOKEN,
        channel_id=CHANNEL_ID
    )