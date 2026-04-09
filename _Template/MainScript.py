"""
Main Script.py
----------------
Entry point for the Main Script.

Lifecycle
---------
1.  
2.  
3.  
      a. 
      b. 
4.  

Dev / non-Linux behaviour
--------------------------
On non-Linux machines `prod_mode()` returns False and the loop runs exactly
once.  This lets you test locally without an infinite loop.
"""

# std modules
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup path and load environment
sys.path.append(str(Path(__file__).parent.parent.resolve()))
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# universal imports
from utils.config import logger, prod_mode

# local imports
from config import load_var

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False

def _request_shutdown(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum} — shutting down after current cycle.")
    _shutdown_requested = True

signal.signal(signal.SIGTERM, _request_shutdown)
signal.signal(signal.SIGINT,  _request_shutdown)

# ---------------------------------------------------------------------------
# Initialise config
# ---------------------------------------------------------------------------

Config = load_var()

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

try:
    while not _shutdown_requested:

        # ── Main Method structure goes here! ──────────────────────────────

        # ── Break after one cycle on dev machines ─────────────────────────
        if not prod_mode():
            logger.info("Non-Linux environment — exiting after one cycle (dev mode).")
            break

except Exception:
    logger.exception("Unexpected error in Main Script")

finally:
    # ── Always notify on exit ─────────────────────────────────────────────
    logger.info("Main Script Shutdown Notice.")