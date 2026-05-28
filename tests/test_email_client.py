from datetime import date

from ride_connector.email_client import EmailClient
from ride_connector.models import DailyBriefing


def test_email_message_contains_plain_text_and_html() -> None:
    briefing = DailyBriefing(
        briefing_date=date(2026, 5, 27),
        training_summary="Z2 / 60分钟",
        status_summary="体重77.8kg",
        training_advice="按计划",
        nutrition_advice="补水并保持轻微热量缺口",
    )
    client = EmailClient(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password",
        sender="from@example.com",
        recipient="to@example.com",
    )

    message = client.build_message(briefing)
    rendered = message.as_string()

    assert "RideConnector" in message["Subject"]
    assert "from@example.com" == message["From"]
    assert "to@example.com" == message["To"]
    assert "text/plain" in rendered
    assert "text/html" in rendered


def test_email_message_includes_feedback_url() -> None:
    briefing = DailyBriefing(
        briefing_date=date(2026, 5, 27),
        training_summary="Z2",
        status_summary="正常",
        training_advice="按计划",
        nutrition_advice="补水",
        feedback_url="https://github.com/example/repo/issues/new?template=daily-feedback.yml",
    )
    client = EmailClient(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password",
        sender="from@example.com",
        recipient="to@example.com",
    )

    message = client.build_message(briefing)
    rendered = "\n".join(
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in message.walk()
        if part.get_content_type() in {"text/plain", "text/html"}
    )

    assert "填写今日反馈" in rendered
    assert "daily-feedback.yml" in rendered
