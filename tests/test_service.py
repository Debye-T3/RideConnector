from datetime import date

from ride_connector.config import Settings
from ride_connector.models import DailyBriefing, TrainingEvent, WellnessEntry
from ride_connector.service import DailyPushService
from ride_connector.storage import Storage


class FakeIntervals:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def get_events(self, oldest: date, newest: date) -> list[TrainingEvent]:
        if self.fail:
            raise RuntimeError("intervals down")
        return [TrainingEvent.from_api({"name": "Z2", "duration": 3600})]

    def get_wellness(self, oldest: date, newest: date) -> list[WellnessEntry]:
        return [WellnessEntry.from_api({"id": newest.isoformat(), "weight": 77.5})]


class FakeGenerator:
    def generate(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
    ) -> DailyBriefing:
        return DailyBriefing(
            briefing_date=briefing_date,
            training_summary="Z2 / 60分钟",
            status_summary="体重77.5kg",
            training_advice="按计划",
            nutrition_advice="补水",
        )


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[DailyBriefing] = []

    def send_briefing(self, briefing: DailyBriefing) -> None:
        self.sent.append(briefing)


def make_settings(tmp_path, notifier: str = "email") -> Settings:
    return Settings(
        INTERVALS_API_KEY="intervals",
        NOTIFIER=notifier,
        EMAIL_SMTP_HOST="smtp.example.com",
        EMAIL_SMTP_USER="user",
        EMAIL_SMTP_PASSWORD="password",
        EMAIL_FROM="from@example.com",
        EMAIL_TO="to@example.com",
        WECHAT_APP_ID="appid",
        WECHAT_APP_SECRET="secret",
        WECHAT_TEMPLATE_ID="template",
        WECHAT_OPENID="openid",
        DATABASE_PATH=str(tmp_path / "test.sqlite3"),
    )


def test_daily_push_success_saves_snapshot_and_sends_email(tmp_path) -> None:
    settings = make_settings(tmp_path)
    storage = Storage(settings.database_path)
    notifier = FakeNotifier()
    service = DailyPushService(
        settings,
        storage=storage,
        intervals_client=FakeIntervals(),
        briefing_generator=FakeGenerator(),
        email_client=notifier,
    )

    service.run_once(date(2026, 5, 27))

    assert notifier.sent[0].training_summary == "Z2 / 60分钟"


def test_daily_push_sends_failure_notice_when_intervals_fails(tmp_path) -> None:
    settings = make_settings(tmp_path)
    notifier = FakeNotifier()
    service = DailyPushService(
        settings,
        storage=Storage(settings.database_path),
        intervals_client=FakeIntervals(fail=True),
        briefing_generator=FakeGenerator(),
        email_client=notifier,
    )

    service.run_once(date(2026, 5, 27))

    assert notifier.sent[0].training_summary == "今日数据读取失败"


def test_daily_push_can_still_use_wechat_notifier(tmp_path) -> None:
    settings = make_settings(tmp_path, notifier="wechat")
    notifier = FakeNotifier()
    service = DailyPushService(
        settings,
        storage=Storage(settings.database_path),
        intervals_client=FakeIntervals(),
        briefing_generator=FakeGenerator(),
        wechat_client=notifier,
    )

    service.run_once(date(2026, 5, 27))

    assert notifier.sent[0].training_summary == "Z2 / 60分钟"

