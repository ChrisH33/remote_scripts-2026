from datetime import timedelta
from dataclasses import dataclass
from typing import Dict
from dotenv import load_dotenv
from utils.config import require_env

# -------------------------------------------------
# Shared mutable state (used across modules)
# These dicts are imported by message_builder.py and mutated in-place,
# so they must live here (one source of truth).
# -------------------------------------------------
active_block_state: dict[str, str] = {}   # script_name → colour string e.g. "green"
script_history:     dict[str, list] = {}  # script_name → list of datetime start times
block_start_time:   dict[str, object] = {} # script_name → datetime of last state change

# -------------------------------------------------
# Environment variables
# -------------------------------------------------
load_dotenv()
SLACK_BOT_TOKEN = require_env("SLACK_BOT_TOKEN")
CHANNEL_ID      = require_env("SLACK_CHANNEL_RemoteLog")

# -------------------------------------------------
# Config dataclass
# -------------------------------------------------
@dataclass(frozen=True)
class Config:
    max_blocks:    int
    cycle_time:    timedelta   # BUG FIX: was annotated as `int` but assigned a timedelta
    refresh_rate:  int
    keywords:      list[str]
    status_header: str
    emoji_map:     Dict[str, str]
    slack_bot_token: str
    channel_id:    str


def load_var() -> Config:
    return Config(
        max_blocks=15,
        cycle_time=timedelta(minutes=1),   # how long a "red" entry lingers before removal
        refresh_rate=20,                   # seconds between Slack updates
        keywords=['launcher', 'debugpy', 'pythonw.exe'],  # processes to ignore
        status_header="Remote Ubuntu Dashboard :skull:",
        emoji_map={
            "green":  ":large_green_square:",   # script is running
            "red":    ":large_red_square:",     # script recently stopped
            "orange": ":large_orange_square:",  # reserved / future use
            "grey":   ":black_large_square:",   # unknown / placeholder
        },
        slack_bot_token=SLACK_BOT_TOKEN,
        channel_id=CHANNEL_ID,
    )