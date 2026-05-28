from datetime import date

from ride_connector.ai import daily_checkin_to_dict, merge_status_with_checkin
from ride_connector.models import DailyCheckin


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
