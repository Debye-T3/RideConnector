from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ride_connector.config import parse_score
from ride_connector.models import DailyCheckin, to_float


@dataclass(frozen=True)
class DailyFeedback:
    feedback_date: date
    weight_kg: float | None
    checkin: DailyCheckin


HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
DATE_RE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")


def parse_issue_form_body(body: str) -> DailyFeedback:
    fields = extract_issue_form_fields(body)
    date_text = require_field(fields, "date")
    feedback_date = parse_feedback_date(date_text)

    weight = parse_optional_float(fields.get("weight_kg", ""))
    return DailyFeedback(
        feedback_date=feedback_date,
        weight_kg=weight,
        checkin=DailyCheckin(
            bedtime=empty_to_none(fields.get("bedtime", "")),
            fatigue=parse_score(fields.get("fatigue", "")),
            soreness=parse_score(fields.get("soreness", "")),
            research_pressure=parse_score(fields.get("research_pressure", "")),
            notes=empty_to_none(fields.get("notes", "")),
        ),
    )


def extract_issue_form_fields(body: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        match = HEADING_RE.match(line)
        if match:
            current_key = normalize_label(match.group(1))
            fields[current_key] = []
            continue
        if current_key is not None:
            fields[current_key].append(line)
    return {key: cleanup_value("\n".join(lines)) for key, lines in fields.items()}


def normalize_label(label: str) -> str:
    label = label.strip().lower()
    known = {
        "date": "date",
        "日期": "date",
        "weight_kg": "weight_kg",
        "体重": "weight_kg",
        "体重 kg": "weight_kg",
        "体重（kg）": "weight_kg",
        "bedtime": "bedtime",
        "入睡时间": "bedtime",
        "fatigue": "fatigue",
        "主观疲劳": "fatigue",
        "soreness": "soreness",
        "腿部酸痛": "soreness",
        "research_pressure": "research_pressure",
        "科研压力": "research_pressure",
        "notes": "notes",
        "备注": "notes",
    }
    return known.get(label, label.replace(" ", "_"))


def cleanup_value(value: str) -> str:
    value = value.strip()
    if value in {"_No response_", "No response", "无响应"}:
        return ""
    return value


def require_field(fields: dict[str, str], key: str) -> str:
    value = fields.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing required field: {key}")
    return value


def parse_optional_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    parsed = to_float(value)
    if parsed is None:
        raise ValueError(f"Invalid number: {value}")
    return parsed


def empty_to_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_feedback_date(value: str) -> date:
    match = DATE_RE.match(value)
    if not match:
        raise ValueError("date must be in YYYY-MM-DD format")
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError("date must be a valid calendar date") from exc
