from __future__ import annotations

import json
from datetime import date

import httpx

from ride_connector.advice import build_fallback_briefing, compact_context, summarize_status, summarize_training
from ride_connector.models import DailyBriefing, DailyCheckin, FeedbackDecision, TrainingEvent, WellnessEntry


EXTRA_TRAINING_KEYWORDS = ("想加练", "加练", "有空训练", "想骑", "可以训练", "安排训练")


class BriefingGenerator:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        weight_loss_mode: bool = True,
        athlete_profile: str = "",
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.weight_loss_mode = weight_loss_mode
        self.athlete_profile = athlete_profile.strip()
        self._client = client or httpx.Client(timeout=30)
        self.last_feedback_decision: FeedbackDecision | None = None

    def generate(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
        daily_checkin: DailyCheckin | None = None,
        mode: str = "morning",
    ) -> DailyBriefing:
        fallback = build_fallback_briefing(
            briefing_date, events, wellness, weight_loss_mode=self.weight_loss_mode
        )
        fallback = apply_title_and_checkin(fallback, daily_checkin, mode)
        self.last_feedback_decision = None
        if not self.api_key:
            return fallback

        try:
            payload = self._request_ai(briefing_date, events, wellness, daily_checkin, mode)
            if mode == "feedback":
                self.last_feedback_decision = parse_feedback_decision(payload)
            return DailyBriefing(
                briefing_date=briefing_date,
                training_summary=summarize_training(events),
                status_summary=merge_status_with_checkin(summarize_status(wellness), daily_checkin),
                training_advice=payload.get("training_advice") or fallback.training_advice,
                nutrition_advice=payload.get("nutrition_advice") or fallback.nutrition_advice,
                title=title_for_mode(mode),
            )
        except Exception:
            return fallback

    def _request_ai(
        self,
        briefing_date: date,
        events: list[TrainingEvent],
        wellness: list[WellnessEntry],
        daily_checkin: DailyCheckin | None,
        mode: str,
    ) -> dict[str, object]:
        has_planned_training = bool(events)
        wants_optional_activity = wants_extra_training(daily_checkin)
        system = (
            "你是周浩洋的自行车训练晨报教练。建议要直接、具体、像教练，不要空泛鼓励。"
            "你可以根据长期个人画像、今日课表、Intervals wellness 数据和今日主观反馈做动态调整。"
            "feedback 模式下，如果训练无需更改且健康状态没有明显风险，不要为了礼貌触发第二封邮件。"
            "如果当天没有计划训练，禁止主动安排结构化训练、功率区间、间歇、LSD、Sweet Spot 或 VO2。"
            "只有用户在反馈备注里明确表示想加练或今天有空训练时，才允许给可选轻量活动方案，且必须标注“可选，不是计划要求”。"
            "不要给医疗诊断，不要鼓励带病硬顶，不要建议极端节食。"
            "输出必须是 JSON object，包含 training_advice、nutrition_advice、should_send_email、alert_reason、severity。"
        )
        user = {
            "date": briefing_date.isoformat(),
            "mode": mode,
            "has_planned_training": has_planned_training,
            "wants_optional_activity": wants_optional_activity,
            "send_email_policy": {
                "default": "feedback 模式默认不发第二封邮件。",
                "send_only_if": [
                    "训练需要降级、缩短、取消或改为恢复安排",
                    "健康或恢复状态急需注意",
                    "用户明确想加练且需要提醒边界",
                ],
                "do_not_send_if": "训练无需更改，且无健康风险或恢复风险。",
                "severity_values": ["none", "info", "warning", "urgent"],
            },
            "no_plan_day_policy": {
                "default": "不主动加练；优先恢复、生活安排、科研压力管理和饮食控制。",
                "forbidden_when_no_plan": ["结构化训练", "功率区间", "间歇", "LSD", "Sweet Spot", "VO2"],
                "allowed": ["完全休息判断", "轻松活动边界", "拉伸/散步作为放松", "饮食补水", "睡眠建议"],
                "optional_activity_rule": "仅当 wants_optional_activity=true 时，给可选轻量活动，并标注可选、不是计划要求。",
            },
            "athlete_profile": self.athlete_profile or "未配置长期个人画像。",
            "daily_checkin": daily_checkin_to_dict(daily_checkin),
            "current_goal": "提升FTP和Z2稳定性，在不牺牲训练质量与科研恢复的前提下温和减脂。",
            "intervals_data": compact_context(events, wellness),
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
                "temperature": 0.35,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return dict(parsed)


def parse_feedback_decision(payload: dict[str, object]) -> FeedbackDecision:
    should_send = payload.get("should_send_email")
    return FeedbackDecision(
        should_send_email=bool(should_send) if should_send is not None else False,
        alert_reason=str(payload.get("alert_reason") or ""),
        severity=str(payload.get("severity") or "none"),
    )


def wants_extra_training(daily_checkin: DailyCheckin | None) -> bool:
    notes = (daily_checkin.notes or "") if daily_checkin else ""
    return any(keyword in notes for keyword in EXTRA_TRAINING_KEYWORDS)


def daily_checkin_to_dict(daily_checkin: DailyCheckin | None) -> dict[str, object]:
    if daily_checkin is None or not daily_checkin.has_any_value():
        return {"filled": False}
    return {
        "filled": True,
        "bedtime": daily_checkin.bedtime,
        "subjective_fatigue_1_10": daily_checkin.fatigue,
        "leg_soreness_1_10": daily_checkin.soreness,
        "research_pressure_1_10": daily_checkin.research_pressure,
        "notes": daily_checkin.notes,
    }


def apply_title_and_checkin(
    briefing: DailyBriefing,
    daily_checkin: DailyCheckin | None,
    mode: str,
) -> DailyBriefing:
    return DailyBriefing(
        briefing_date=briefing.briefing_date,
        training_summary=briefing.training_summary,
        status_summary=merge_status_with_checkin(briefing.status_summary, daily_checkin),
        training_advice=briefing.training_advice,
        nutrition_advice=briefing.nutrition_advice,
        title=title_for_mode(mode),
        feedback_url=briefing.feedback_url,
    )


def title_for_mode(mode: str) -> str:
    return "动态调整" if mode == "feedback" else "骑行晨报"


def merge_status_with_checkin(status_summary: str, daily_checkin: DailyCheckin | None) -> str:
    if daily_checkin is None or not daily_checkin.has_any_value():
        return status_summary
    return f"{status_summary}；主观输入：{daily_checkin.summary()}"
