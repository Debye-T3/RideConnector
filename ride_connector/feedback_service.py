from __future__ import annotations

import logging
from datetime import timedelta

from ride_connector.ai import BriefingGenerator
from ride_connector.config import Settings
from ride_connector.feedback import DailyFeedback, parse_issue_form_body
from ride_connector.github_client import GitHubClient
from ride_connector.intervals_client import IntervalsClient
from ride_connector.models import DailyBriefing
from ride_connector.service import DailyPushService
from ride_connector.storage import Storage

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(
        self,
        settings: Settings,
        storage: Storage | None = None,
        intervals_client: IntervalsClient | None = None,
        briefing_generator: BriefingGenerator | None = None,
        github_client: GitHubClient | None = None,
        push_service: DailyPushService | None = None,
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
        self.github_client = github_client or GitHubClient(
            repository=settings.github_repository,
            token=settings.github_token,
            api_url=settings.github_api_url,
        )
        self.push_service = push_service or DailyPushService(
            settings,
            storage=self.storage,
            intervals_client=self.intervals_client,
            briefing_generator=self.briefing_generator,
        )

    def handle_issue(self, issue_number: int) -> None:
        issue = self.github_client.get_issue(issue_number)
        feedback = parse_issue_form_body(str(issue.get("body", "")))
        try:
            self.process_feedback(feedback)
        except Exception as exc:
            self.github_client.comment_issue(
                issue_number,
                f"反馈已收到，但处理失败：`{exc}`\n\n请检查输入或 Actions 日志。",
            )
            raise
        self.github_client.comment_issue(
            issue_number,
            "已写回体重（如填写）并发送动态调整邮件。",
        )
        self.github_client.close_issue(issue_number)

    def process_feedback(self, feedback: DailyFeedback) -> None:
        if feedback.weight_kg is not None:
            self.intervals_client.update_wellness_weight(feedback.feedback_date, feedback.weight_kg)

        events = self.intervals_client.get_events(feedback.feedback_date, feedback.feedback_date)
        wellness_start = feedback.feedback_date - timedelta(days=13)
        wellness = self.intervals_client.get_wellness(wellness_start, feedback.feedback_date)
        self.storage.save_snapshot(
            feedback.feedback_date.isoformat(),
            "feedback",
            {
                "weight_kg": feedback.weight_kg,
                "daily_checkin": feedback.checkin.summary(),
            },
        )
        briefing = self.briefing_generator.generate(
            feedback.feedback_date,
            events,
            wellness,
            daily_checkin=feedback.checkin,
            mode="feedback",
        )
        self.push_service.send_briefing(
            DailyBriefing(
                briefing_date=briefing.briefing_date,
                training_summary=briefing.training_summary,
                status_summary=briefing.status_summary,
                training_advice=briefing.training_advice,
                nutrition_advice=briefing.nutrition_advice,
                title="动态调整",
            )
        )
