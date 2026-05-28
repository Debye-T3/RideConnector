from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ride_connector.models import DailyBriefing


class EmailClient:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        sender: str,
        recipient: str,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender = sender
        self.recipient = recipient
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def send_briefing(self, briefing: DailyBriefing) -> None:
        message = self.build_message(briefing)
        smtp_cls = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        with smtp_cls(self.smtp_host, self.smtp_port, timeout=20) as smtp:
            if self.use_tls and not self.use_ssl:
                smtp.starttls()
            smtp.login(self.smtp_user, self.smtp_password)
            smtp.sendmail(self.sender, [self.recipient], message.as_string())

    def build_message(self, briefing: DailyBriefing) -> MIMEMultipart:
        subject = f"RideConnector {briefing.title} {briefing.briefing_date.isoformat()}"
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = self.recipient
        message.attach(MIMEText(self.build_text(briefing), "plain", "utf-8"))
        message.attach(MIMEText(self.build_html(briefing), "html", "utf-8"))
        return message

    @staticmethod
    def build_text(briefing: DailyBriefing) -> str:
        lines = [
            f"RideConnector {briefing.title} {briefing.briefing_date.isoformat()}",
            "",
            f"今日训练：{briefing.training_summary}",
            f"身体状态：{briefing.status_summary}",
            f"训练建议：{briefing.training_advice}",
            f"饮食补水：{briefing.nutrition_advice}",
        ]
        if briefing.feedback_url:
            lines.extend(["", f"填写今日反馈并重新生成建议：{briefing.feedback_url}"])
        return "\n".join(lines)

    @staticmethod
    def build_html(briefing: DailyBriefing) -> str:
        rows = [
            ("今日训练", briefing.training_summary),
            ("身体状态", briefing.status_summary),
            ("训练建议", briefing.training_advice),
            ("饮食补水", briefing.nutrition_advice),
        ]
        rows_html = "\n".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
            for label, value in rows
        )
        feedback_html = ""
        if briefing.feedback_url:
            feedback_html = (
                '<p class="action"><a href="'
                + html.escape(briefing.feedback_url, quote=True)
                + '">填写今日反馈并重新生成建议</a></p>'
            )
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; }}
    .container {{ max-width: 680px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 22px; margin: 0 0 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; text-align: left; }}
    th {{ width: 96px; color: #374151; background: #f9fafb; }}
    .action a {{ display: inline-block; margin-top: 18px; padding: 10px 14px; color: #ffffff; background: #2563eb; border-radius: 6px; text-decoration: none; }}
    .note {{ margin-top: 16px; color: #6b7280; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>RideConnector {html.escape(briefing.title)} {html.escape(briefing.briefing_date.isoformat())}</h1>
    <table>{rows_html}</table>
    {feedback_html}
    <p class="note">建议仅供训练和营养安排参考，不替代医生、营养师或教练意见。</p>
  </div>
</body>
</html>"""
