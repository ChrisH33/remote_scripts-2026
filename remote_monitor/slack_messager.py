"""
slack_messager.py
-----------------
Entry point for the remote monitor.  Initialises Slack, then loops
every `refresh_rate` seconds to scan running processes and push an
updated Block Kit message to the configured channel.
"""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Make sure the project root is on the path so sibling packages resolve
project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))

# BUG FIX: `import UniFunction` / `UniFunction.prod_mode()` does not exist.
# prod_mode() is defined in utils/config.py — import it from there instead.
from utils.config import prod_mode
from utils.slack_wrapper import SlackClientWrapper

# Local modules
from config import load_var, active_block_state
from message_builder import build_slack_blocks, update_live_status, rollover_blocks
from process_scan import get_active_scripts

# =============================================================================
# Initialise config & Slack client
# =============================================================================
config       = load_var()
slack_wrapper = SlackClientWrapper(bot_token=config.slack_bot_token)

# Post the initial (empty) dashboard message and keep its timestamp so we can
# update the same message on every iteration instead of spamming new ones.
blocks = build_slack_blocks(config.status_header, config.max_blocks, config.emoji_map)
ts     = slack_wrapper.send_message(channel=config.channel_id, text="Remote monitor", blocks=blocks)

# =============================================================================
# Main monitoring loop
# =============================================================================
while True:
    # 1. Find which Python scripts are currently running on this machine
    currently_active_scripts = get_active_scripts(config.keywords)

    # 2. Update in-memory state (green / red / remove) based on what's running
    update_live_status(currently_active_scripts, config.cycle_time)

    # 3. Trim the oldest entries if we've exceeded the display limit
    rollover_blocks(active_block_state, config.max_blocks)

    # 4. Rebuild the Block Kit payload and push it to Slack
    blocks = build_slack_blocks(config.status_header, config.max_blocks, config.emoji_map)
    slack_wrapper.update_message(
        message_ts=ts,
        channel=config.channel_id,
        text="Remote monitor",
        blocks=blocks,
    )

    # 5. On non-Linux machines (dev) run only once so the loop can be tested
    if not prod_mode():
        break

    time.sleep(config.refresh_rate)