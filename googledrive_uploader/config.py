from datetime import timedelta


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