from datetime import date

from ride_connector.config import Settings
from ride_connector.feedback import DailyFeedback
from ride_connector.feedback_service import FeedbackService
from ride_connector.models import DailyBriefing, DailyCheckin, TrainingEvent, WellnessEntry
from ride_connector.storage import Storage


class FakeIntervals:
    def __init__(self) -> None:
        self.updated_weight: tuple[date, float] | None = None

    def update_wellness_weight(self, entry_date: date, weight_kg: float) -> dict:
        self.updated_weight = (entry_date, weight_kg)
        return {"weight": weight_kg}

    def get_events(self, oldest: date, newest: date) -> list[TrainingEvent]:
        return [TrainingEvent.from_api({"name": "Z2", "duration": 3600})]

    def get_wellness(self, oldest: date, newest: date) -> list[WellnessEntry]:
        return [WellnessEntry.from_api({"id": newest.isoformat(), "weight": 71.4})]


class FakeGenerator:
    def __init__(self) -> None:
        self.mode: str | None = None

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
            training_summary="Z2 / 60分钟",
            status_summary=daily_checkin.summary() if daily_checkin else "正常",
            training_advice="降级为Z1/Z2",
            nutrition_advice="训练前补碳水",
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


def test_feedback_service_writes_weight_and_sends_revised_email(tmp_path) -> None:
    intervals = FakeIntervals()
    generator = FakeGenerator()
    push = FakePush()
    service = FeedbackService(
        make_settings(tmp_path),
        storage=Storage(str(tmp_path / "test.sqlite3")),
        intervals_client=intervals,
        briefing_generator=generator,
        github_client=FakeGitHub(),
        push_service=push,
    )
    feedback = DailyFeedback(
        feedback_date=date(2026, 5, 28),
        weight_kg=71.4,
        checkin=DailyCheckin(bedtime="01:20", fatigue=7),
    )

    service.process_feedback(feedback)

    assert intervals.updated_weight == (date(2026, 5, 28), 71.4)
    assert generator.mode == "feedback"
    assert push.sent[0].title == "动态调整"
