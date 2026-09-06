"""Root workspace wrapper for run_agent_demo.py."""

import os
import sys

FEEDCRAFT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedcraft")
if FEEDCRAFT_DIR not in sys.path:
    sys.path.insert(0, FEEDCRAFT_DIR)

from run_agent_demo import run_agent_demo

if __name__ == "__main__":
    run_agent_demo()
