from datetime import date

import httpx

from ride_connector.config import DEFAULT_TEMPLATE_FIELD_MAP
from ride_connector.models import DailyBriefing
from ride_connector.storage import Storage
from ride_connector.wechat_client import WeChatClient


def make_briefing() -> DailyBriefing:
    return DailyBriefing(
        briefing_date=date(2026, 5, 27),
        training_summary="今日无计划训练",
        status_summary="体重77.8kg",
        training_advice="轻松恢复",
        nutrition_advice="保持轻微热量缺口",
    )


def test_build_template_payload_uses_configurable_mapping(tmp_path) -> None:
    storage = Storage(str(tmp_path / "test.sqlite3"))
    client = WeChatClient(
        app_id="appid",
        app_secret="secret",
        template_id="template",
        openid="openid",
        field_map={**DEFAULT_TEMPLATE_FIELD_MAP, "training": "thing2"},
        storage=storage,
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))),
    )

    payload = client.build_template_payload(make_briefing())

    assert payload["touser"] == "openid"
    assert payload["data"]["thing2"]["value"] == "今日无计划训练"
    assert payload["data"]["remark"]["value"] == "保持轻微热量缺口"


def test_send_briefing_refreshes_expired_token_and_retries(tmp_path) -> None:
    storage = Storage(str(tmp_path / "test.sqlite3"))
    storage.set_json("wechat_access_token", {"access_token": "old", "expires_at": 4102444800})
    seen_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/message/template/send"):
            token = request.url.params["access_token"]
            seen_tokens.append(token)
            if token == "old":
                return httpx.Response(200, json={"errcode": 42001, "errmsg": "expired"})
            return httpx.Response(200, json={"errcode": 0, "msgid": 1})
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "new", "expires_in": 7200})
        return httpx.Response(404)

    client = WeChatClient(
        app_id="appid",
        app_secret="secret",
        template_id="template",
        openid="openid",
        field_map=DEFAULT_TEMPLATE_FIELD_MAP,
        storage=storage,
        base_url="https://wechat.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.send_briefing(make_briefing())

    assert seen_tokens == ["old", "new"]

