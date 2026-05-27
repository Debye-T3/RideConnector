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

    def validate_runtime(self) -> None:
        missing = [
            name
            for name, value in {
                "INTERVALS_API_KEY": self.intervals_api_key,
                "WECHAT_APP_ID": self.wechat_app_id,
                "WECHAT_APP_SECRET": self.wechat_app_secret,
                "WECHAT_TEMPLATE_ID": self.wechat_template_id,
                "WECHAT_OPENID": self.wechat_openid,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()

