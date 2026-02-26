"""
process_scan.py
---------------
Scans the host machine for running Python scripts.

Returns a set of script *names* (without path or .py extension) so they
can be tracked in the dashboard.  Processes whose command lines contain
any of the configured `keywords` are ignored (e.g. debuggers, launchers).
"""

# std modules
import os
import psutil


def get_active_scripts(keywords: list[str]) -> set[str]:
    """
    Return the base names (no extension) of all Python scripts currently
    running on this machine, excluding any whose command line contains a
    keyword from `keywords`.

    Examples
    --------
    >>> get_active_scripts(["debugpy", "launcher"])
    {'my_pipeline', 'data_sync'}
    """
    scripts: set[str] = set()

    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmd = proc.info["cmdline"]

            # Skip processes with no command line or that aren't Python
            if not cmd or "python" not in os.path.basename(cmd[0]).lower():
                continue

            for arg in cmd[1:]:
                arg_lower = arg.lower()

                # Skip interpreter flags and noise strings
                if any(keyword in arg_lower for keyword in keywords):
                    break   # skip the whole process, not just this arg

                # Only record real .py files that exist on disk
                if arg_lower.endswith(".py") and os.path.isfile(arg):
                    scripts.add(os.path.splitext(os.path.basename(arg))[0])
                    break   # one script name per process

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process vanished or we don't have permission — skip silently
            continue

    return scripts