from datetime import date

from ride_connector.advice import (
    build_fallback_briefing,
    summarize_status,
    summarize_training,
    weight_trend,
)
from ride_connector.models import TrainingEvent, WellnessEntry


def test_summarize_training_with_multiple_events() -> None:
    events = [
        TrainingEvent.from_api(
            {"name": "Endurance", "duration": 3600, "distance": 30000, "icu_training_load": 45}
        ),
        TrainingEvent.from_api({"name": "Core"}),
    ]

    assert summarize_training(events) == "Endurance / 60分钟 / 30.0公里 / 负荷45；Core"


def test_summarize_training_without_events() -> None:
    assert summarize_training([]) == "今日无计划训练"


def test_status_uses_latest_available_weight_and_sleep_values() -> None:
    entries = [
        WellnessEntry.from_api({"id": "2026-05-20", "weight": 78.5}),
        WellnessEntry.from_api({"id": "2026-05-26", "weight": 77.8, "sleepSecs": 25200}),
        WellnessEntry.from_api(
            {
                "id": "2026-05-27",
                "restingHR": 68,
                "hrv": 42,
                "fatigue": 8,
            }
        ),
    ]

    summary = summarize_status(entries)

    assert "体重77.8kg" in summary
    assert "睡眠7.0h" in summary
    assert "近周期体重下降0.7kg" in summary
    assert "疲劳偏高" in summary


def test_weight_trend_requires_two_values() -> None:
    assert weight_trend([WellnessEntry.from_api({"id": "2026-05-27", "weight": 77.8})]) is None


def test_fallback_briefing_recovery_day_weight_loss() -> None:
    briefing = build_fallback_briefing(date(2026, 5, 27), [], [], weight_loss_mode=True)

    assert briefing.training_summary == "今日无计划训练"
    assert "恢复" in briefing.training_advice
    assert "轻微热量缺口" in briefing.nutrition_advice

