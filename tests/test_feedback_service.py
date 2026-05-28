from datetime import date

from ride_connector.config import Settings
from ride_connector.feedback import DailyFeedback
from ride_connector.feedback_service import FeedbackService, deterministic_feedback_decision
from ride_connector.models import DailyBriefing, DailyCheckin, FeedbackDecision, TrainingEvent, WellnessEntry
from ride_connector.storage import Storage


class FakeIntervals:
    def __init__(self, events: list[TrainingEvent] | None = None) -> None:
        self.updated_weight: tuple[date, float] | None = None
        self.events = events if events is not None else [TrainingEvent.from_api({"name": "Z2", "duration": 3600})]

    def update_wellness_weight(self, entry_date: date, weight_kg: float) -> dict:
        self.updated_weight = (entry_date, weight_kg)
        return {"weight": weight_kg}

    def get_events(self, oldest: date, newest: date) -> list[TrainingEvent]:
        return self.events

    def get_wellness(self, oldest: date, newest: date) -> list[WellnessEntry]:
        return [WellnessEntry.from_api({"id": newest.isoformat(), "weight": 71.4, "sleepSecs": 25200})]


class FakeGenerator:
    def __init__(self, decision: FeedbackDecision | None = None) -> None:
        self.mode: str | None = None
        self.last_feedback_decision = decision

    def generate(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
        daily_checkin: DailyCheckin | None = None,
        mode: str = "morning",
    ) -> DailyBriefing:
        self.mode = mode
        return DailyBriefing(
            briefing_date=briefing_date,
            training_summary="Z2 / 60分钟" if events else "今日无计划训练",
            status_summary=daily_checkin.summary() if daily_checkin else "正常",
            training_advice="按计划即可",
            nutrition_advice="正常补水",
            title="动态调整",
        )


class FakePush:
    def __init__(self) -> None:
        self.sent: list[DailyBriefing] = []

    def send_briefing(self, briefing: DailyBriefing) -> None:
        self.sent.append(briefing)


class FakeGitHub:
    pass


def make_settings(tmp_path) -> Settings:
    return Settings(
        INTERVALS_API_KEY="intervals",
        EMAIL_SMTP_HOST="smtp.example.com",
        EMAIL_SMTP_USER="user",
        EMAIL_SMTP_PASSWORD="password",
        EMAIL_FROM="from@example.com",
        EMAIL_TO="to@example.com",
        GITHUB_REPOSITORY="owner/repo",
        GITHUB_TOKEN="token",
        DATABASE_PATH=str(tmp_path / "test.sqlite3"),
    )


def make_service(
    tmp_path,
    intervals: FakeIntervals | None = None,
    generator: FakeGenerator | None = None,
    push: FakePush | None = None,
) -> tuple[FeedbackService, FakeIntervals, FakeGenerator, FakePush]:
    intervals = intervals or FakeIntervals()
    generator = generator or FakeGenerator()
    push = push or FakePush()
    service = FeedbackService(
        make_settings(tmp_path),
        storage=Storage(str(tmp_path / "test.sqlite3")),
        intervals_client=intervals,
        briefing_generator=generator,
        github_client=FakeGitHub(),
        push_service=push,
    )
    return service, intervals, generator, push


def test_feedback_service_writes_weight_but_stays_silent_for_normal_feedback(tmp_path) -> None:
    service, intervals, generator, push = make_service(tmp_path)
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=71.4,
        checkin=DailyCheckin(bedtime="01:20", fatigue=5, soreness=3, research_pressure=5),
    )

    result = service.process_feedback(feedback)

    assert intervals.updated_weight == (date(2026, 5, 28), 71.4)
    assert generator.mode == "feedback"
    assert result.sent_email is False
    assert push.sent == []
    assert "未发现需要额外提醒" in result.comment


def test_feedback_service_sends_email_for_high_fatigue(tmp_path) -> None:
    service, _, _, push = make_service(tmp_path)
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=None,
        checkin=DailyCheckin(fatigue=8),
    )

    result = service.process_feedback(feedback)

    assert result.sent_email is True
    assert push.sent[0].title == "动态调整"
    assert "主观疲劳≥8" in result.comment


def test_feedback_service_sends_email_when_ai_requests_alert(tmp_path) -> None:
    service, _, _, push = make_service(
        tmp_path,
        generator=FakeGenerator(FeedbackDecision(True, "AI判断需要降级", "warning")),
    )
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=None,
        checkin=DailyCheckin(fatigue=5),
    )

    result = service.process_feedback(feedback)

    assert result.sent_email is True
    assert push.sent[0].title == "动态调整"
    assert "AI判断需要降级" in result.comment


def test_no_plan_day_normal_feedback_stays_silent(tmp_path) -> None:
    service, _, _, push = make_service(tmp_path, intervals=FakeIntervals(events=[]))
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=None,
        checkin=DailyCheckin(fatigue=4, soreness=2),
    )

    result = service.process_feedback(feedback)

    assert result.sent_email is False
    assert push.sent == []


def test_no_plan_day_risk_keyword_sends_email(tmp_path) -> None:
    service, _, _, push = make_service(tmp_path, intervals=FakeIntervals(events=[]))
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=None,
        checkin=DailyCheckin(notes="昨晚通宵，今天明显不适"),
    )

    result = service.process_feedback(feedback)

    assert result.sent_email is True
    assert push.sent[0].title == "动态调整"
    assert "风险词" in result.comment


def test_deterministic_decision_triggers_for_high_scores() -> None:
    decision = deterministic_feedback_decision(
        DailyFeedback(
            feedback_date=date(2026, 5, 28),
            weight_kg=None,
            checkin=DailyCheckin(fatigue=8, soreness=8, research_pressure=9),
        ),
        has_planned_training=True,
        wellness=[],
    )

    assert decision.should_send_email is True
    assert "主观疲劳≥8" in decision.alert_reason
    assert "腿部酸痛≥8" in decision.alert_reason
    assert "科研压力≥9" in decision.alert_reason
