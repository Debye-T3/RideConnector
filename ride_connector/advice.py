from __future__ import annotations

from dataclasses import asdict
from datetime import date

from ride_connector.models import DailyBriefing, TrainingEvent, WellnessEntry


def summarize_training(events: list[TrainingEvent]) -> str:
    if not events:
        return "今日无计划训练"

    parts: list[str] = []
    for event in events:
        details = [event.name]
        if event.duration_seconds:
            details.append(f"{round(event.duration_seconds / 60)}分钟")
        if event.distance_meters:
            details.append(f"{event.distance_meters / 1000:.1f}公里")
        if event.load:
            details.append(f"负荷{event.load:.0f}")
        parts.append(" / ".join(details))
    return "；".join(parts)


def summarize_status(briefing_date: date, entries: list[WellnessEntry]) -> str:
    if not entries:
        return "近期生理状态未记录"

    sorted_entries = sort_entries(entries)
    today = entry_for_date(sorted_entries, briefing_date)
    latest_weight = today.weight if today else None
    latest_sleep = today.sleep_hours if today else None
    latest_resting_hr = today.resting_hr if today else None
    latest_hrv = today.hrv if today else None

    parts: list[str] = []
    parts.append(f"体重{latest_weight:.1f}kg" if latest_weight else "体重未记录")
    parts.append(f"睡眠{latest_sleep:.1f}h" if latest_sleep else "睡眠未记录")
    parts.append(f"静息心率{latest_resting_hr:.0f}" if latest_resting_hr else "静息心率未记录")
    parts.append(f"HRV {latest_hrv:.0f}" if latest_hrv else "HRV未记录")

    trend = weight_trend(sorted_entries)
    if trend:
        parts.append(trend)

    flags = readiness_flags(today) if today else []
    if flags:
        parts.append("；".join(flags))
    return "，".join(parts)


def sort_entries(entries: list[WellnessEntry]) -> list[WellnessEntry]:
    dated = [entry for entry in entries if entry.entry_date is not None]
    if dated:
        return sorted(dated, key=lambda entry: entry.entry_date)
    return entries


def entry_for_date(entries: list[WellnessEntry], target_date: date) -> WellnessEntry | None:
    for entry in reversed(entries):
        if entry.entry_date == target_date:
            return entry
    return None


def weight_trend(entries: list[WellnessEntry]) -> str | None:
    weights = [entry.weight for entry in entries if entry.weight is not None]
    if len(weights) < 2:
        return None
    delta = weights[-1] - weights[0]
    if abs(delta) < 0.2:
        return "体重趋势稳定"
    direction = "下降" if delta < 0 else "上升"
    return f"近周期体重{direction}{abs(delta):.1f}kg"


def readiness_flags(entry: WellnessEntry) -> list[str]:
    flags: list[str] = []
    if entry.sleep_hours is not None and entry.sleep_hours < 6:
        flags.append("睡眠偏少，今天避免硬顶")
    if entry.fatigue is not None and entry.fatigue >= 7:
        flags.append("疲劳偏高")
    if entry.soreness is not None and entry.soreness >= 7:
        flags.append("酸痛偏高")
    if entry.resting_hr is not None and entry.resting_hr >= 65:
        flags.append("静息心率偏高，留意恢复")
    return flags


def fallback_training_advice(events: list[TrainingEvent], wellness: list[WellnessEntry]) -> str:
    sorted_wellness = sort_entries(wellness)
    latest = sorted_wellness[-1] if sorted_wellness else None
    flags = readiness_flags(latest) if latest else []
    if not events:
        base = "今日无计划训练，不主动加练；优先恢复、睡眠和科研安排。"
        if flags:
            return f"{base}当前状态提示：{'；'.join(flags)}。轻松散步或拉伸只作为放松，不作为必须完成的训练。"
        return f"{base}如有活动需求，仅保留轻松散步或拉伸，不安排结构化骑行。"
    if flags:
        return "按计划开始，但把体感放在第一位；若热身后仍疲劳，降低强度或缩短主课。"
    return "按计划完成训练，重点控制目标强度，不为追数据额外加量。"


def fallback_nutrition_advice(events: list[TrainingEvent], weight_loss_mode: bool = True) -> str:
    has_training = bool(events)
    if has_training and weight_loss_mode:
        return "训练前后保留必要碳水，正餐提高蛋白和蔬菜比例；全天保持轻微热量缺口，补足水和电解质。"
    if has_training:
        return "训练前补少量易消化碳水，训练后补蛋白和主食，注意补水与电解质。"
    if weight_loss_mode:
        return "无计划训练日控制零食和含糖饮料，保证蛋白、蔬菜和饮水，维持轻微热量缺口。"
    return "无计划训练日正常均衡饮食，优先蛋白、蔬菜和充足饮水。"


def build_fallback_briefing(
    briefing_date: date,
    events: list[TrainingEvent],
    wellness: list[WellnessEntry],
    weight_loss_mode: bool = True,
) -> DailyBriefing:
    return DailyBriefing(
        briefing_date=briefing_date,
        training_summary=summarize_training(events),
        status_summary=summarize_status(briefing_date, wellness),
        training_advice=fallback_training_advice(events, wellness),
        nutrition_advice=fallback_nutrition_advice(events, weight_loss_mode),
    )


def compact_context(
    events: list[TrainingEvent],
    wellness: list[WellnessEntry],
    briefing_date: date | None = None,
) -> dict[str, object]:
    today_wellness = entry_for_date(wellness, briefing_date) if briefing_date else None
    history = [
        entry
        for entry in wellness
        if briefing_date is None or entry.entry_date != briefing_date
    ]
    return {
        "training_events": [asdict(event) for event in events],
        "today_wellness": asdict(today_wellness) if today_wellness else None,
        "recent_wellness_history": [asdict(entry) for entry in history],
    }
