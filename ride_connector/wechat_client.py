from __future__ import annotations

import time
from typing import Any

import httpx

from ride_connector.models import DailyBriefing
from ride_connector.storage import Storage


class WeChatClient:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        template_id: str,
        openid: str,
        field_map: dict[str, str],
        storage: Storage,
        base_url: str = "https://api.weixin.qq.com",
        client: httpx.Client | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.template_id = template_id
        self.openid = openid
        self.field_map = field_map
        self.storage = storage
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=20)

    def send_briefing(self, briefing: DailyBriefing) -> dict[str, Any]:
        payload = self.build_template_payload(briefing)
        token = self.get_access_token()
        response = self._send_payload(token, payload)
        if response.get("errcode") in {40001, 40014, 42001}:
            token = self.refresh_access_token()
            response = self._send_payload(token, payload)
        if response.get("errcode", 0) != 0:
            raise RuntimeError(f"WeChat template send failed: {response}")
        return response

    def build_template_payload(self, briefing: DailyBriefing) -> dict[str, Any]:
        values = {
            "first": "今日骑行晨报",
            "date": briefing.briefing_date.isoformat(),
            "training": briefing.training_summary,
            "status": briefing.status_summary,
            "advice": briefing.training_advice,
            "nutrition": briefing.nutrition_advice,
        }
        data = {
            self.field_map[key]: {"value": value}
            for key, value in values.items()
            if key in self.field_map
        }
        return {
            "touser": self.openid,
            "template_id": self.template_id,
            "data": data,
        }

    def get_access_token(self) -> str:
        cached = self.storage.get_json("wechat_access_token")
        now = int(time.time())
        if cached and cached.get("access_token") and int(cached.get("expires_at", 0)) > now + 60:
            return str(cached["access_token"])
        return self.refresh_access_token()

    def refresh_access_token(self) -> str:
        response = self._client.get(
            f"{self.base_url}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        if "access_token" not in data:
            raise RuntimeError(f"WeChat access token request failed: {data}")
        expires_in = int(data.get("expires_in", 7200))
        self.storage.set_json(
            "wechat_access_token",
            {
                "access_token": data["access_token"],
                "expires_at": int(time.time()) + max(expires_in - 120, 60),
            },
        )
        return str(data["access_token"])

    def _send_payload(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{self.base_url}/cgi-bin/message/template/send",
            params={"access_token": access_token},
            json=payload,
        )
        response.raise_for_status()
        return response.json()

