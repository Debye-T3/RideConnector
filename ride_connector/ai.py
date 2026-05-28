from __future__ import annotations

import json
from datetime import date

import httpx

from ride_connector.advice import build_fallback_briefing, compact_context, summarize_status, summarize_training
from ride_connector.models import DailyBriefing, DailyCheckin, TrainingEvent, WellnessEntry


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
        if not self.api_key:
            return fallback

        try:
            payload = self._request_ai(briefing_date, events, wellness, daily_checkin, mode)
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
    ) -> dict[str, str]:
        has_planned_training = bool(events)
        wants_optional_activity = wants_extra_training(daily_checkin)
        system = (
            "你是周浩洋的自行车训练晨报教练。建议要直接、具体、像教练，不要空泛鼓励。"
            "你可以根据长期个人画像、今日课表、Intervals wellness 数据和今日主观反馈做动态调整。"
            "如果当天有计划训练，每次都要明确是否按计划执行、是否降级、建议功率或心率控制、时长、熔断条件、补给和饮食重点。"
            "如果当天没有计划训练，禁止主动安排结构化训练、功率区间、间歇、LSD、Sweet Spot 或 VO2；"
            "只能输出恢复建议、是否适合完全休息、轻松活动边界、饮食/补水/体重管理、睡眠和科研压力建议。"
            "只有用户在反馈备注里明确表示想加练或今天有空训练时，才允许给可选轻量活动方案，且必须标注“可选，不是计划要求”。"
            "不要给医疗诊断，不要鼓励带病硬顶，不要建议极端节食。"
            "如果数据缺失，要明确按缺失处理，不要编造。"
            "输出必须是 JSON object，只包含 training_advice 和 nutrition_advice 两个字符串字段。"
        )
        if mode == "feedback":
            mode_instruction = (
                "这是收到当天主观反馈后的二次动态调整。请优先判断原训练计划是否需要改变。"
                "如果无计划训练且用户未明确想加练，不要给新增训练方案。"
            )
        else:
            mode_instruction = "这是早晨初始晨报。请基于课表和已知 wellness 给出当天初步建议。"
        user = {
            "date": briefing_date.isoformat(),
            "mode": mode,
            "mode_instruction": mode_instruction,
            "has_planned_training": has_planned_training,
            "wants_optional_activity": wants_optional_activity,
            "no_plan_day_policy": {
                "default": "不主动加练；优先恢复、生活安排、科研压力管理和饮食控制。",
                "forbidden_when_no_plan": ["结构化训练", "功率区间", "间歇", "LSD", "Sweet Spot", "VO2"],
                "allowed": ["完全休息判断", "轻松活动边界", "拉伸/散步作为放松", "饮食补水", "睡眠建议"],
                "optional_activity_rule": "仅当 wants_optional_activity=true 时，给可选轻量活动，并标注可选、不是计划要求。",
            },
            "athlete_profile": self.athlete_profile or "未配置长期个人画像。",
            "daily_checkin": daily_checkin_to_dict(daily_checkin),
            "current_goal": "提升FTP和Z2稳定性，在不牺牲训练质量与科研恢复的前提下温和减脂。",
            "decision_requirements": [
                "使用176W工作FTP作为默认功率基准，除非输入数据明确更新。",
                "如果睡眠、疲劳、腿部酸痛或科研压力偏差，要主动建议降级或休息。",
                "如果当天是VO2、阈值、Sweet Spot或长LSD，要给出训练前后碳水和补水建议。",
                "如果无计划训练，饮食建议应以减脂友好、蛋白和蔬菜优先、不过度节食为主。",
                "建议必须短而具体，适合放进每日邮件。",
            ],
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
        return {str(key): str(value) for key, value in parsed.items()}


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
