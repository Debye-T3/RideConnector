from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from ride_connector.ai import BriefingGenerator
from ride_connector.config import Settings
from ride_connector.email_client import EmailClient
from ride_connector.intervals_client import IntervalsClient
from ride_connector.models import DailyBriefing, TrainingEvent, WellnessEntry
from ride_connector.storage import Storage
from ride_connector.wechat_client import WeChatClient

logger = logging.getLogger(__name__)


class DailyPushService:
    def __init__(
        self,
        settings: Settings,
        storage: Storage | None = None,
        intervals_client: IntervalsClient | None = None,
        briefing_generator: BriefingGenerator | None = None,
        email_client: EmailClient | None = None,
        wechat_client: WeChatClient | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage or Storage(settings.database_path)
        self.intervals_client = intervals_client or IntervalsClient(
            api_key=settings.intervals_api_key,
            athlete_id=settings.intervals_athlete_id,
            base_url=settings.intervals_base_url,
        )
        self.briefing_generator = briefing_generator or BriefingGenerator(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            weight_loss_mode=settings.weight_loss_mode,
            athlete_profile=settings.athlete_profile,
        )
        self.email_client = email_client
        self.wechat_client = wechat_client
        self.sleep_fn = sleep_fn or time.sleep

        if settings.notifier == "email" and self.email_client is None:
            self.email_client = EmailClient(
                smtp_host=settings.email_smtp_host,
                smtp_port=settings.email_smtp_port,
                smtp_user=settings.email_smtp_user,
                smtp_password=settings.email_smtp_password,
                sender=settings.email_from,
                recipient=settings.email_to,
                use_tls=settings.email_use_tls,
                use_ssl=settings.email_use_ssl,
            )
        if settings.notifier == "wechat" and self.wechat_client is None:
            self.wechat_client = WeChatClient(
                app_id=settings.wechat_app_id,
                app_secret=settings.wechat_app_secret,
                template_id=settings.wechat_template_id,
                openid=settings.wechat_openid,
                field_map=settings.wechat_template_field_map,
                storage=self.storage,
                base_url=settings.wechat_base_url,
            )

    def run_once(self, run_date: date | None = None) -> None:
        target_date = run_date or date.today()
        try:
            try:
                events, wellness = self.fetch_daily_data(target_date)
            except Exception as exc:
                briefing = DailyBriefing(
                    briefing_date=target_date,
                    training_summary="今日数据读取失败",
                    status_summary="Intervals.icu 暂时不可用",
                    training_advice="请稍后直接查看 Intervals.icu；今天训练以原计划和身体感受为准。",
                    nutrition_advice="饮食按常规骑行日处理：保证蛋白、蔬菜、饮水和必要碳水，避免因数据缺失临时极端节食。",
                )
                self.send_briefing(briefing)
                self.storage.log_push(target_date.isoformat(), "partial_failure", str(exc))
                logger.exception("Intervals data fetch failed for %s", target_date.isoformat())
                return

            self.storage.save_snapshot(
                target_date.isoformat(),
                "intervals",
                {
                    "events": [event.raw for event in events],
                    "wellness": [entry.raw for entry in wellness],
                    "daily_checkin": self.settings.daily_checkin.summary(),
                },
            )
            briefing = self.briefing_generator.generate(
                target_date,
                events,
                wellness,
                daily_checkin=self.settings.daily_checkin,
            )
            if self.settings.resolved_feedback_form_url:
                briefing = DailyBriefing(
                    briefing_date=briefing.briefing_date,
                    training_summary=briefing.training_summary,
                    status_summary=briefing.status_summary,
                    training_advice=briefing.training_advice,
                    nutrition_advice=briefing.nutrition_advice,
                    title=briefing.title,
                    feedback_url=self.settings.resolved_feedback_form_url,
                )
            self.send_briefing(briefing)
            self.storage.log_push(target_date.isoformat(), "success", "briefing sent")
            logger.info("Daily briefing sent for %s", target_date.isoformat())
        except Exception as exc:
            self.storage.log_push(target_date.isoformat(), "failure", str(exc))
            logger.exception("Daily briefing failed for %s", target_date.isoformat())
            raise

    def fetch_daily_data(
        self, target_date: date
    ) -> tuple[list[TrainingEvent], list[WellnessEntry]]:
        wellness_start = target_date - timedelta(days=13)
        attempts = self.settings.sleep_wait_attempts if self.settings.wait_for_sleep else 1
        attempts = max(1, attempts)
        events = []
        wellness = []
        for attempt in range(attempts):
            events = self.intervals_client.get_events(target_date, target_date)
            wellness = self.intervals_client.get_wellness(wellness_start, target_date)
            if not self.settings.wait_for_sleep or has_today_sleep(wellness, target_date):
                break
            if attempt < attempts - 1:
                logger.info(
                    "Sleep data not available for %s; waiting %s seconds before retry",
                    target_date.isoformat(),
                    self.settings.sleep_poll_seconds,
                )
                self.sleep_fn(self.settings.sleep_poll_seconds)
        return events, wellness

    def send_briefing(self, briefing: DailyBriefing) -> None:
        if self.settings.notifier == "email":
            if self.email_client is None:
                raise RuntimeError("Email notifier is not configured")
            self.email_client.send_briefing(briefing)
            return
        if self.settings.notifier == "wechat":
            if self.wechat_client is None:
                raise RuntimeError("WeChat notifier is not configured")
            self.wechat_client.send_briefing(briefing)
            return
        raise RuntimeError(f"Unsupported notifier: {self.settings.notifier}")


def today_in_timezone(timezone: str) -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo(timezone)).date()


def has_today_sleep(wellness: list[WellnessEntry], target_date: date) -> bool:
    return any(entry.entry_date == target_date and entry.sleep_hours is not None for entry in wellness)
