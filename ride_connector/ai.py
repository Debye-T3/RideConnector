from __future__ import annotations

import json
from datetime import date

import httpx

from ride_connector.advice import build_fallback_briefing, compact_context, summarize_status, summarize_training
from ride_connector.models import DailyBriefing, TrainingEvent, WellnessEntry


class BriefingGenerator:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        weight_loss_mode: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.weight_loss_mode = weight_loss_mode
        self._client = client or httpx.Client(timeout=30)

    def generate(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
    ) -> DailyBriefing:
        fallback = build_fallback_briefing(
            briefing_date, events, wellness, weight_loss_mode=self.weight_loss_mode
        )
        if not self.api_key:
            return fallback

        try:
            payload = self._request_ai(briefing_date, events, wellness)
            return DailyBriefing(
                briefing_date=briefing_date,
                training_summary=summarize_training(events),
                status_summary=summarize_status(wellness),
                training_advice=payload.get("training_advice") or fallback.training_advice,
                nutrition_advice=payload.get("nutrition_advice") or fallback.nutrition_advice,
            )
        except Exception:
            return fallback

    def _request_ai(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
    ) -> dict[str, str]:
        system = (
            "你是保守的自行车训练晨报助手。不要替代医生、营养师或教练。"
            "不要编造未提供的数据。不要建议用户临时大幅增加训练量。"
            "输出必须是 JSON，字段为 training_advice 和 nutrition_advice。"
        )
        user = {
            "date": briefing_date.isoformat(),
            "goal": "在保证骑行训练营养和恢复的前提下降低体重",
            "constraints": [
                "建议简短，适合微信公众号模板消息",
                "训练建议低风险：按计划、降低强度、关注恢复、补给重点",
                "饮食建议强调轻微热量缺口、蛋白、蔬菜、水和电解质",
            ],
            "data": compact_context(events, wellness),
        }
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {str(key): str(value) for key, value in parsed.items()}

