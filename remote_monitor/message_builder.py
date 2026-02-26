"""
message_builder.py
------------------
Builds Slack Block Kit payloads and manages the in-memory state that
tracks which Python scripts are running on the remote machine.

Shared state (active_block_state, script_history, block_start_time) lives
in config.py and is imported here so all modules mutate the *same* dicts.
"""

# std modules
from datetime import datetime, timedelta

# local modules
from config import active_block_state, block_start_time, script_history

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_elapsed(start: datetime) -> str:
    """Return a human-readable elapsed time string, e.g. '  `5m 12s`'."""
    elapsed = datetime.now() - start
    total_secs = int(elapsed.total_seconds())
    mins, secs = divmod(total_secs, 60)
    hours, mins = divmod(mins, 60)

    if hours:
        return f"  `{hours}h {mins}m`"
    return f"  `{mins}m {secs}s`"


# ---------------------------------------------------------------------------
# Block builder
# ---------------------------------------------------------------------------

def build_slack_blocks(status_header: str, max_blocks: int, emoji_map: dict) -> list:
    """
    Assemble a Slack Block Kit payload from the current active_block_state.

    Returns a list of block dicts ready to pass to chat.postMessage /
    chat.update.  The list is always valid even when no scripts are running.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": status_header, "emoji": True},
        },
        {"type": "divider"},
    ]

    # Cap at max_blocks to stay within Slack's 50-block hard limit
    visible = list(active_block_state.items())[:max_blocks]

    for script_name, status in visible:
        emoji    = emoji_map.get(status, emoji_map["grey"])
        start_dt = block_start_time.get(script_name)
        time_str = _format_elapsed(start_dt) if start_dt else ""

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji}  *{script_name}*{time_str}",
            },
        })

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

    Transitions:
    - New script detected       → green, record start time, append to history
    - Script still running      → ensure green (re-greenify if it came back)
    - Script disappeared        → red, record stop time
    - Script red for ≥ cycle_time → remove entirely
    """
    now = datetime.now()

    # ── Scripts that are currently running ──────────────────────────────
    for script in currently_active:
        current_status = active_block_state.get(script)

        if current_status is None:
            # First time we see this script
            active_block_state[script] = "green"
            block_start_time[script]   = now
            script_history.setdefault(script, []).append(now)

        elif current_status != "green":
            # Script was red (briefly stopped and restarted) — re-greenify
            active_block_state[script] = "green"
            block_start_time[script]   = now
            script_history.setdefault(script, []).append(now)

        # else: already green and still running — nothing to do

    # ── Scripts that are no longer running ──────────────────────────────
    for script in list(active_block_state.keys()):
        if script in currently_active:
            continue

        if active_block_state[script] == "green":
            # Just stopped — flag red
            active_block_state[script] = "red"
            block_start_time[script]   = now

        elif active_block_state[script] == "red":
            # Already red — evict once the linger period expires
            stopped_at = block_start_time.get(script)
            if stopped_at and (now - stopped_at) >= cycle_time:
                del active_block_state[script]
                block_start_time.pop(script, None)


# ---------------------------------------------------------------------------
# Block rollover  (overflow eviction)
# ---------------------------------------------------------------------------

def rollover_blocks(state: dict, max_blocks: int) -> None:
    """
    Evict the oldest entries when tracked scripts exceed max_blocks.

    Python dicts preserve insertion order (3.7+), so the first key is
    always the oldest.  Prefer evicting red (stopped) entries first to
    avoid hiding scripts that are still running.
    """
    # First pass: prefer evicting stale red entries
    if len(state) > max_blocks:
        red_keys = [k for k, v in state.items() if v == "red"]
        for key in red_keys:
            if len(state) <= max_blocks:
                break
            del state[key]
            block_start_time.pop(key, None)

    # Second pass: fall back to oldest-first eviction
    while len(state) > max_blocks:
        oldest = next(iter(state))
        del state[oldest]
        block_start_time.pop(oldest, None)