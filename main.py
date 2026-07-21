"""Workflow-compatible entry point for the Calibration Bridge secondary bot.

The upstream GitHub workflows call ``main.py``. Keeping this small adapter means those
workflow files remain byte-for-byte upstream while all forecasting logic lives in the
clearly named secondary implementation.
"""

from __future__ import annotations

import argparse
import logging

from secondary_bot import run


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run Calibration Bridge secondary bot")
    parser.add_argument(
        "--mode",
        choices=["test_questions", "tournament"],
        default="tournament",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required guard for live Summer FutureEval and MiniBench forecasts",
    )
    arguments = parser.parse_args()
    run(arguments.mode, arguments.confirm_live)
