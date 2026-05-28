from __future__ import annotations

import argparse
import logging

from ride_connector.config import get_settings
from ride_connector.feedback_service import FeedbackService
from ride_connector.jobs.daily_push import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Process RideConnector daily feedback issue.")
    parser.add_argument("--issue-number", type=int, required=True)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    settings.validate_runtime()
    succeeded = FeedbackService(settings).handle_issue_safely(args.issue_number)
    if not succeeded:
        return
    logging.getLogger(__name__).info("Processed feedback issue #%s", args.issue_number)


if __name__ == "__main__":
    main()
