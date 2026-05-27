from __future__ import annotations

import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ride_connector.config import get_settings
from ride_connector.service import DailyPushService, today_in_timezone


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Intervals.icu daily WeChat briefing.")
    parser.add_argument("--once", action="store_true", help="Run one push immediately and exit.")
    parser.add_argument("--skip-validation", action="store_true", help="Skip required env validation.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    if not args.skip_validation:
        settings.validate_runtime()

    service = DailyPushService(settings)
    if args.once:
        service.run_once(today_in_timezone(settings.timezone))
        return

    timezone = ZoneInfo(settings.timezone)
    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        lambda: service.run_once(today_in_timezone(settings.timezone)),
        CronTrigger(hour=8, minute=0, timezone=timezone),
        id="daily_intervals_wechat_push",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logging.getLogger(__name__).info(
        "Scheduler started at %s, daily push time: 08:00 %s",
        datetime.now(timezone).isoformat(),
        settings.timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    main()

