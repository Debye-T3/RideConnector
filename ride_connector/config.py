from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    wechat_template_field_map: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_TEMPLATE_FIELD_MAP),
        alias="WECHAT_TEMPLATE_FIELD_MAP",
    )

    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

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
    database_path: str = Field(default="data/ride_connector.sqlite3", alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("wechat_template_field_map", mode="before")
    @classmethod
    def parse_template_map(cls, value: Any) -> dict[str, str]:
        if value in (None, ""):
            return dict(DEFAULT_TEMPLATE_FIELD_MAP)
        if isinstance(value, str):
            parsed = json.loads(value)
        else:
            parsed = value
        merged = dict(DEFAULT_TEMPLATE_FIELD_MAP)
        merged.update({str(k): str(v) for k, v in parsed.items()})
        return merged

    @field_validator("notifier")
    @classmethod
    def normalize_notifier(cls, value: str) -> str:
        return value.strip().lower()

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
