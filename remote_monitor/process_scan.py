import psutil
import os

def get_active_scripts(keywords: list[str]) -> set[str]:
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
                    scripts.add(os.path.splitext(os.path.basename(arg))[0])
                    break
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return scripts
