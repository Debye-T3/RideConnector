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
