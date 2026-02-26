"""
message_builder.py
------------------
Builds Slack Block Kit payloads and manages the in-memory state that
tracks which Python scripts are running on the remote machine.

Shared state (active_block_state, script_history, block_start_time) lives
in config.py and is imported here so that all modules mutate the *same* dicts.
"""

from datetime import datetime, timedelta

# BUG FIX: this file was an exact copy-paste of config.py.
# It must import shared state from config (not redefine it),
# otherwise mutations here would be invisible to slack_messager.py.
from config import active_block_state, script_history, block_start_time


# ---------------------------------------------------------------------------
# Block builder
# ---------------------------------------------------------------------------

def build_slack_blocks(status_header: str, max_blocks: int, emoji_map: dict) -> list:
    """
    Assemble a Slack Block Kit payload from the current active_block_state.

    Returns a list of block dicts ready to pass to chat.postMessage / chat.update.
    """
    blocks = [
        # ── Header row ──────────────────────────────────────────────────────
        {
            "type": "header",
            "text": {"type": "plain_text", "text": status_header, "emoji": True},
        },
        {"type": "divider"},
    ]

    # Grab at most max_blocks entries so we never exceed Slack's 50-block limit
    visible = list(active_block_state.items())[:max_blocks]

    for script_name, status in visible:
        emoji    = emoji_map.get(status, emoji_map["grey"])
        start_dt = block_start_time.get(script_name)

        # Show how long the script has been in its current state
        if start_dt:
            elapsed = datetime.now() - start_dt
            mins, secs = divmod(int(elapsed.total_seconds()), 60)
            time_str = f"  `{mins}m {secs}s`"
        else:
            time_str = ""

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji}  *{script_name}*{time_str}",
            },
        })

    # Friendly fallback when nothing is running
    if not visible:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":zzz: No scripts currently running"},
        })

    return blocks


# ---------------------------------------------------------------------------
# Live-status updater
# ---------------------------------------------------------------------------

def update_live_status(currently_active: set[str], cycle_time: timedelta) -> None:
    """
    Reconcile active_block_state with the set of scripts seen right now.

    Rules:
    - Script just appeared  → mark green, record start time
    - Script still running  → keep green (no change)
    - Script disappeared    → mark red, record the stop time
    - Script has been red for >= cycle_time → remove it entirely
    """
    now = datetime.now()

    # ── Handle scripts that are currently running ────────────────────────
    for script in currently_active:
        if script not in active_block_state:
            # First time we see this script
            active_block_state[script] = "green"
            block_start_time[script]   = now
            script_history.setdefault(script, []).append(now)
        else:
            # Already tracked — make sure colour is green (could have been red)
            if active_block_state[script] != "green":
                active_block_state[script] = "green"
                block_start_time[script]   = now

    # ── Handle scripts that are no longer running ────────────────────────
    for script in list(active_block_state.keys()):
        if script in currently_active:
            continue  # still running, handled above

        if active_block_state[script] == "green":
            # Script just stopped — flag it red and note when it stopped
            active_block_state[script] = "red"
            block_start_time[script]   = now

        elif active_block_state[script] == "red":
            # Already red — check whether it has lingered long enough to remove
            stopped_at = block_start_time.get(script)
            if stopped_at and (now - stopped_at) >= cycle_time:
                del active_block_state[script]
                block_start_time.pop(script, None)


# ---------------------------------------------------------------------------
# Block rollover
# ---------------------------------------------------------------------------

def rollover_blocks(state: dict, max_blocks: int) -> None:
    """
    Evict the oldest entries when the number of tracked scripts exceeds
    max_blocks. Python dicts preserve insertion order (3.7+), so the first
    key is always the oldest.
    """
    while len(state) > max_blocks:
        oldest = next(iter(state))   # oldest inserted key
        del state[oldest]
        block_start_time.pop(oldest, None)   # clean up companion dict