import json
from datetime import date

import httpx

from ride_connector.ai import (
    BriefingGenerator,
    daily_checkin_to_dict,
    merge_status_with_checkin,
    title_for_mode,
    wants_extra_training,
)
from ride_connector.models import DailyCheckin, TrainingEvent


def test_daily_checkin_to_dict_marks_empty_input() -> None:
    assert daily_checkin_to_dict(DailyCheckin()) == {"filled": False}


def test_daily_checkin_to_dict_maps_manual_inputs() -> None:
    checkin = DailyCheckin(
        bedtime="01:20",
        fatigue=7,
        soreness=4,
        research_pressure=8,
        notes="上午有实验",
    )

    assert daily_checkin_to_dict(checkin) == {
        "filled": True,
        "bedtime": "01:20",
        "subjective_fatigue_1_10": 7,
        "leg_soreness_1_10": 4,
        "research_pressure_1_10": 8,
        "notes": "上午有实验",
    }


def test_merge_status_with_checkin_appends_summary() -> None:
    checkin = DailyCheckin(bedtime="01:20", fatigue=7)

    assert merge_status_with_checkin("体重77.5kg", checkin) == "体重77.5kg；主观输入：入睡时间01:20，主观疲劳7/10"


def test_title_for_feedback_mode() -> None:
    assert title_for_mode("feedback") == "动态调整"


def test_wants_extra_training_requires_explicit_note() -> None:
    assert wants_extra_training(DailyCheckin(notes="今天实验压力大")) is False
    assert wants_extra_training(DailyCheckin(notes="下午有空训练，想加练一点")) is True


def test_ai_payload_marks_no_planned_training_and_forbids_structure() -> None:
    seen_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "training_advice": "今日无计划训练，优先恢复。",
                                    "nutrition_advice": "控制零食，保证蛋白。",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    generator = BriefingGenerator(
        base_url="https://ai.test/v1",
        api_key="key",
        model="model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    generator.generate(date(2026, 5, 28), [], [], mode="feedback")

    user_payload = json.loads(seen_payload["messages"][1]["content"])
    assert user_payload["has_planned_training"] is False
    assert user_payload["wants_optional_activity"] is False
    assert "结构化训练" in user_payload["no_plan_day_policy"]["forbidden_when_no_plan"]


def test_ai_payload_allows_optional_activity_when_user_asks() -> None:
    seen_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "training_advice": "可选，不是计划要求：只做轻松活动。",
                                    "nutrition_advice": "正常吃饭。",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    generator = BriefingGenerator(
        base_url="https://ai.test/v1",
        api_key="key",
        model="model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    generator.generate(
        date(2026, 5, 28),
        [],
        [],
        daily_checkin=DailyCheckin(notes="今天有空训练，想加练一点"),
        mode="feedback",
    )

    user_payload = json.loads(seen_payload["messages"][1]["content"])
    assert user_payload["has_planned_training"] is False
    assert user_payload["wants_optional_activity"] is True


def test_ai_payload_marks_planned_training() -> None:
    seen_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "training_advice": "按计划完成。",
                                    "nutrition_advice": "训练前补碳水。",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    generator = BriefingGenerator(
        base_url="https://ai.test/v1",
        api_key="key",
        model="model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    generator.generate(
        date(2026, 5, 28),
        [TrainingEvent.from_api({"name": "Z2", "duration": 3600})],
        [],
    )

    user_payload = json.loads(seen_payload["messages"][1]["content"])
    assert user_payload["has_planned_training"] is True
