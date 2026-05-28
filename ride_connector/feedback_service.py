from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from ride_connector.ai import BriefingGenerator
from ride_connector.config import Settings
from ride_connector.feedback import DailyFeedback, parse_issue_form_body
from ride_connector.github_client import GitHubClient
from ride_connector.intervals_client import IntervalsClient
from ride_connector.models import DailyBriefing, FeedbackDecision, WellnessEntry
from ride_connector.service import DailyPushService
from ride_connector.storage import Storage

logger = logging.getLogger(__name__)

RISK_KEYWORDS = ("感冒", "发热", "发烧", "胸闷", "咳嗽加重", "咳嗽", "通宵", "明显不适", "头晕", "乏力")


@dataclass(frozen=True)
class FeedbackResult:
    sent_email: bool
    comment: str
    decision: FeedbackDecision


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
            result = self.process_feedback(feedback)
        except Exception as exc:
            self.github_client.comment_issue(
                issue_number,
                f"反馈已收到，但处理失败：`{exc}`\n\n请检查输入或 Actions 日志。",
            )
            raise
        self.github_client.comment_issue(issue_number, result.comment)
        self.github_client.close_issue(issue_number)

    def handle_issue_safely(self, issue_number: int) -> bool:
        try:
            self.handle_issue(issue_number)
            return True
        except Exception:
            logger.exception("Feedback issue #%s failed", issue_number)
            return False

    def process_feedback(self, feedback: DailyFeedback) -> FeedbackResult:
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
        ai_decision = self.briefing_generator.last_feedback_decision
        rule_decision = deterministic_feedback_decision(feedback, bool(events), wellness)
        decision = combine_decisions(ai_decision, rule_decision)

        if decision.should_send_email:
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
            return FeedbackResult(
                sent_email=True,
                decision=decision,
                comment=f"已写回体重（如填写）并发送动态调整邮件。原因：{decision.alert_reason or '需要重要提醒'}",
            )

        return FeedbackResult(
            sent_email=False,
            decision=decision,
            comment="已写回体重（如填写）；未发现需要额外提醒的训练或健康风险，因此未发送第二封邮件。",
        )


def deterministic_feedback_decision(
    feedback: DailyFeedback,
    has_planned_training: bool,
    wellness: list[WellnessEntry],
) -> FeedbackDecision:
    reasons: list[str] = []
    checkin = feedback.checkin
    if checkin.fatigue is not None and checkin.fatigue >= 8:
        reasons.append("主观疲劳≥8")
    if checkin.soreness is not None and checkin.soreness >= 8:
        reasons.append("腿部酸痛≥8")
    if checkin.research_pressure is not None and checkin.research_pressure >= 9:
        reasons.append("科研压力≥9")
    notes = checkin.notes or ""
    matched_keywords = [keyword for keyword in RISK_KEYWORDS if keyword in notes]
    if matched_keywords:
        reasons.append("备注出现风险词：" + "、".join(matched_keywords))
    latest_sleep = latest_wellness_value(wellness, "sleep_hours")
    if has_planned_training and latest_sleep is not None and latest_sleep < 6:
        reasons.append("有计划训练且睡眠<6小时")

    if reasons:
        severity = "urgent" if any("发热" in reason or "胸闷" in reason for reason in reasons) else "warning"
        return FeedbackDecision(True, "；".join(reasons), severity)
    return FeedbackDecision(False)


def combine_decisions(
    ai_decision: FeedbackDecision | None,
    rule_decision: FeedbackDecision,
) -> FeedbackDecision:
    if rule_decision.should_send_email:
        return rule_decision
    if ai_decision and ai_decision.should_send_email:
        return ai_decision
    return FeedbackDecision(False)


def latest_wellness_value(wellness: list[WellnessEntry], field_name: str) -> float | None:
    for entry in reversed(wellness):
        value = getattr(entry, field_name)
        if value is not None:
            return value
    return None
