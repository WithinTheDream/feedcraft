"""Workspace root wrapper for run_demo.py."""

import os
import sys

FEEDCRAFT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedcraft")
if FEEDCRAFT_DIR not in sys.path:
    sys.path.insert(0, FEEDCRAFT_DIR)

from run_demo import run_demo

if __name__ == "__main__":
    run_demo()
