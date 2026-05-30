from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ride_connector.models import DailyCheckin


DEFAULT_TEMPLATE_FIELD_MAP = {
    "first": "first",
    "date": "keyword1",
    "training": "keyword2",
    "status": "keyword3",
    "advice": "keyword4",
    "nutrition": "remark",
}


class Settings(BaseSettings):
    intervals_api_key: str = Field(default="", alias="INTERVALS_API_KEY")
    intervals_athlete_id: str = Field(default="0", alias="INTERVALS_ATHLETE_ID")
    intervals_base_url: str = Field(
        default="https://intervals.icu/api/v1", alias="INTERVALS_BASE_URL"
    )

    wechat_app_id: str = Field(default="", alias="WECHAT_APP_ID")
    wechat_app_secret: str = Field(default="", alias="WECHAT_APP_SECRET")
    wechat_template_id: str = Field(default="", alias="WECHAT_TEMPLATE_ID")
    wechat_openid: str = Field(default="", alias="WECHAT_OPENID")
    wechat_base_url: str = Field(default="https://api.weixin.qq.com", alias="WECHAT_BASE_URL")
    wechat_template_field_map_raw: str = Field(default="", alias="WECHAT_TEMPLATE_FIELD_MAP")

    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    athlete_profile: str = Field(default="", alias="ATHLETE_PROFILE")

    daily_bedtime: str = Field(default="", alias="DAILY_BEDTIME")
    daily_fatigue: str = Field(default="", alias="DAILY_FATIGUE")
    daily_soreness: str = Field(default="", alias="DAILY_SORENESS")
    daily_research_pressure: str = Field(default="", alias="DAILY_RESEARCH_PRESSURE")
    daily_checkin_notes: str = Field(default="", alias="DAILY_CHECKIN_NOTES")
    feedback_form_url: str = Field(default="", alias="FEEDBACK_FORM_URL")
    github_repository: str = Field(default="", alias="GITHUB_REPOSITORY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_api_url: str = Field(default="https://api.github.com", alias="GITHUB_API_URL")

    notifier: str = Field(default="email", alias="NOTIFIER")
    email_smtp_host: str = Field(default="", alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, alias="EMAIL_SMTP_PORT")
    email_smtp_user: str = Field(default="", alias="EMAIL_SMTP_USER")
    email_smtp_password: str = Field(default="", alias="EMAIL_SMTP_PASSWORD")
    email_from: str = Field(default="", alias="EMAIL_FROM")
    email_to: str = Field(default="", alias="EMAIL_TO")
    email_use_tls: bool = Field(default=True, alias="EMAIL_USE_TLS")
    email_use_ssl: bool = Field(default=False, alias="EMAIL_USE_SSL")

    timezone: str = Field(default="Asia/Shanghai", alias="TZ")
    weight_loss_mode: bool = Field(default=True, alias="WEIGHT_LOSS_MODE")
    wait_for_sleep: bool = Field(default=False, alias="WAIT_FOR_SLEEP")
    sleep_poll_seconds: int = Field(default=900, alias="SLEEP_POLL_SECONDS")
    sleep_wait_attempts: int = Field(default=13, alias="SLEEP_WAIT_ATTEMPTS")
    database_path: str = Field(default="data/ride_connector.sqlite3", alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("notifier")
    @classmethod
    def normalize_notifier(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def wechat_template_field_map(self) -> dict[str, str]:
        import json

        if not self.wechat_template_field_map_raw.strip():
            return dict(DEFAULT_TEMPLATE_FIELD_MAP)
        parsed = json.loads(self.wechat_template_field_map_raw)
        merged = dict(DEFAULT_TEMPLATE_FIELD_MAP)
        merged.update({str(k): str(v) for k, v in parsed.items()})
        return merged

    @property
    def daily_checkin(self) -> DailyCheckin:
        return DailyCheckin(
            bedtime=self.daily_bedtime.strip() or None,
            fatigue=parse_score(self.daily_fatigue),
            soreness=parse_score(self.daily_soreness),
            research_pressure=parse_score(self.daily_research_pressure),
            notes=self.daily_checkin_notes.strip() or None,
        )

    @property
    def resolved_feedback_form_url(self) -> str:
        if self.feedback_form_url.strip():
            return self.feedback_form_url.strip()
        if self.github_repository.strip():
            return (
                f"https://github.com/{self.github_repository.strip()}/issues/new"
                "?template=daily-feedback.yml"
            )
        return ""

    def validate_runtime(self) -> None:
        common = {"INTERVALS_API_KEY": self.intervals_api_key}
        if self.notifier == "email":
            notifier_settings = {
                "EMAIL_SMTP_HOST": self.email_smtp_host,
                "EMAIL_SMTP_USER": self.email_smtp_user,
                "EMAIL_SMTP_PASSWORD": self.email_smtp_password,
                "EMAIL_FROM": self.email_from,
                "EMAIL_TO": self.email_to,
            }
        elif self.notifier == "wechat":
            notifier_settings = {
                "WECHAT_APP_ID": self.wechat_app_id,
                "WECHAT_APP_SECRET": self.wechat_app_secret,
                "WECHAT_TEMPLATE_ID": self.wechat_template_id,
                "WECHAT_OPENID": self.wechat_openid,
            }
        else:
            raise ValueError("NOTIFIER must be either 'email' or 'wechat'")

        missing = [
            name
            for name, value in {**common, **notifier_settings}.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_score(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    score = int(value)
    if score < 1 or score > 10:
        raise ValueError("Daily check-in scores must be between 1 and 10")
    return score
