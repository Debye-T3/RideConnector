from datetime import date

import pytest

from ride_connector.feedback import extract_issue_form_fields, parse_issue_form_body


ISSUE_BODY = """### date

2026-05-28

### weight_kg

71.4

### bedtime

01:20

### fatigue

7

### soreness

4

### research_pressure

8

### notes

上午有实验
"""


def test_extract_issue_form_fields() -> None:
    fields = extract_issue_form_fields(ISSUE_BODY)

    assert fields["date"] == "2026-05-28"
    assert fields["weight_kg"] == "71.4"
    assert fields["notes"] == "上午有实验"


def test_parse_issue_form_body_complete() -> None:
    feedback = parse_issue_form_body(ISSUE_BODY)

    assert feedback.feedback_date == date(2026, 5, 28)
    assert feedback.weight_kg == 71.4
    assert feedback.checkin.fatigue == 7
    assert feedback.checkin.research_pressure == 8


def test_parse_issue_form_body_accepts_single_digit_month_and_day() -> None:
    feedback = parse_issue_form_body(
        """### date

2026-5-8
"""
    )

    assert feedback.feedback_date == date(2026, 5, 8)


def test_parse_issue_form_body_allows_missing_weight() -> None:
    feedback = parse_issue_form_body(
        """### date

2026-05-28

### weight_kg

_No response_
"""
    )

    assert feedback.weight_kg is None


def test_parse_issue_form_body_rejects_bad_score() -> None:
    with pytest.raises(ValueError, match="between 1 and 10"):
        parse_issue_form_body(
            """### date

2026-05-28

### fatigue

11
"""
        )


def test_parse_issue_form_body_rejects_bad_date() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_issue_form_body(
            """### date

tomorrow
"""
        )
