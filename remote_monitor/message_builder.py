"""
message_builder.py
------------------
Builds Slack Block Kit payloads and manages per-script colour history.

Each cycle, update_live_status() appends a new colour to every script's
history and shifts the window left by dropping the oldest entry once
the history exceeds max_blocks.

Visual format per script:
    *script_name*  :large_green_square: :large_green_square: :large_red_square:
"""

from datetime import datetime, timedelta
from config import active_block_state, block_start_time, script_history


# ---------------------------------------------------------------------------
# Live-status updater
# ---------------------------------------------------------------------------

def update_live_status(
    currently_active: dict[str, float],
    max_blocks: int,
    cycle_time: timedelta,
) -> None:
    """
    Append one colour block to every tracked script this cycle, then trim.

    Colour rules:
      green  — script is running now
      red    — script was running last cycle, now gone
      orange — script was red last cycle and has come back
    
    `currently_active` is the dict from get_active_scripts_with_runtime:
      { script_name: runtime_in_seconds }
    """
    now = datetime.now()
    all_scripts = set(active_block_state.keys()) | set(currently_active.keys())

    for script in all_scripts:
        prev_status = active_block_state.get(script)

        if script in currently_active:
            if prev_status == "red":
                new_status = "orange"   # came back after dropping off
            else:
                new_status = "green"    # running normally (or first seen)

            # Back-fill real start time on first appearance
            if script not in block_start_time:
                runtime = currently_active[script]
                block_start_time[script] = now - timedelta(seconds=runtime)
        else:
            new_status = "red"          # was tracked, now gone

        # Update current status
        active_block_state[script] = new_status

        # Append to rolling history and shift left if over the limit
        history = script_history.setdefault(script, [])
        history.append(new_status)
        if len(history) > max_blocks:
            history.pop(0)


# ---------------------------------------------------------------------------
# Block builder
# ---------------------------------------------------------------------------

def build_slack_blocks(status_header: str, emoji_map: dict) -> list:
    """
    Assemble the Slack Block Kit payload from the current script_history.

    Each script gets one line:
        *script_name*  :green: :green: :red: :green:
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": status_header, "emoji": True},
        },
        {"type": "divider"},
    ]

    if not script_history:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":zzz: No scripts currently running"},
        })
        return blocks

    for script, history in script_history.items():
        emoji_str = "  ".join(emoji_map.get(s, emoji_map["grey"]) for s in history)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{script}*   {emoji_str}",
            },
        })

    return blocks