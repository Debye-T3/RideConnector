from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


def first_present(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return value
    return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class TrainingEvent:
    raw: dict[str, Any]
    name: str
    event_type: str | None = None
    sport: str | None = None
    duration_seconds: int | None = None
    distance_meters: float | None = None
    load: float | None = None
    description: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "TrainingEvent":
        duration = first_present(raw, "duration", "moving_time", "elapsed_time", "planned_time")
        duration_seconds = int(duration) if isinstance(duration, int | float) else None
        return cls(
            raw=raw,
            name=str(first_present(raw, "name", "title", "workout_name") or "未命名训练"),
            event_type=first_present(raw, "type", "category"),
            sport=first_present(raw, "sport", "activity_type"),
            duration_seconds=duration_seconds,
            distance_meters=to_float(first_present(raw, "distance", "planned_distance")),
            load=to_float(first_present(raw, "icu_training_load", "training_load", "load")),
            description=first_present(raw, "description", "notes", "workout_doc"),
        )


@dataclass(frozen=True)
class WellnessEntry:
    raw: dict[str, Any]
    entry_date: date | None
    weight: float | None = None
    resting_hr: float | None = None
    hrv: float | None = None
    sleep_hours: float | None = None
    fatigue: float | None = None
    soreness: float | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "WellnessEntry":
        raw_date = first_present(raw, "id", "date", "day")
        parsed_date = date.fromisoformat(raw_date[:10]) if isinstance(raw_date, str) else None
        sleep = first_present(raw, "sleep", "sleep_time", "sleep_secs", "sleep_seconds")
        sleep_number = to_float(sleep)
        sleep_hours = None
        if sleep_number is not None:
            sleep_hours = sleep_number / 3600 if sleep_number > 24 else sleep_number
        return cls(
            raw=raw,
            entry_date=parsed_date,
            weight=to_float(first_present(raw, "weight", "weight_kg")),
            resting_hr=to_float(first_present(raw, "restingHR", "resting_hr", "restingHeartRate")),
            hrv=to_float(first_present(raw, "hrv", "hrv_rmssd")),
            sleep_hours=sleep_hours,
            fatigue=to_float(first_present(raw, "fatigue")),
            soreness=to_float(first_present(raw, "soreness")),
        )


@dataclass(frozen=True)
class DailyBriefing:
    briefing_date: date
    training_summary: str
    status_summary: str
    training_advice: str
    nutrition_advice: str

