from datetime import date

import httpx

from ride_connector.intervals_client import IntervalsClient
from ride_connector.models import WellnessEntry


def test_get_events_and_wellness_parse_flexible_payloads() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Tempo",
                        "duration": 2700,
                        "distance": 22000,
                        "training_load": 55,
                    }
                ],
            )
        return httpx.Response(200, json=[{"id": "2026-05-27", "weight": 77.6, "sleep": 25200}])

    client = httpx.Client(
        base_url="https://intervals.test/api/v1",
        auth=httpx.BasicAuth("API_KEY", "secret"),
        transport=httpx.MockTransport(handler),
    )
    intervals = IntervalsClient("secret", client=client)

    events = intervals.get_events(date(2026, 5, 27), date(2026, 5, 27))
    wellness = intervals.get_wellness(date(2026, 5, 20), date(2026, 5, 27))

    assert events[0].name == "Tempo"
    assert events[0].load == 55
    assert wellness[0].sleep_hours == 7
    assert requests[0].url.params["oldest"] == "2026-05-27"


def test_wellness_parses_intervals_sleep_secs_camel_case() -> None:
    entry = WellnessEntry.from_api({"id": "2026-05-27", "weightKg": 77.6, "sleepSecs": 28800})

    assert entry.weight == 77.6
    assert entry.sleep_hours == 8


def test_intervals_retries_three_times() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={"error": "temporary"})

    client = httpx.Client(
        base_url="https://intervals.test/api/v1",
        auth=httpx.BasicAuth("API_KEY", "secret"),
        transport=httpx.MockTransport(handler),
    )
    intervals = IntervalsClient("secret", client=client)

    try:
        intervals.get_events(date(2026, 5, 27), date(2026, 5, 27))
    except RuntimeError:
        pass

    assert attempts == 3


def test_update_wellness_weight_merges_existing_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "2026-05-28", "sleepSecs": 28800, "restingHR": 49}],
            )
        if request.method == "PUT":
            payload = json_from_request(request)
            assert payload["id"] == "2026-05-28"
            assert payload["sleepSecs"] == 28800
            assert payload["restingHR"] == 49
            assert payload["weight"] == 71.4
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    client = httpx.Client(
        base_url="https://intervals.test/api/v1",
        auth=httpx.BasicAuth("API_KEY", "secret"),
        transport=httpx.MockTransport(handler),
    )
    intervals = IntervalsClient("secret", client=client)

    result = intervals.update_wellness_weight(date(2026, 5, 28), 71.4)

    assert result["weight"] == 71.4
    assert requests[1].method == "PUT"
    assert requests[1].url.path.endswith("/athlete/0/wellness/2026-05-28")


def json_from_request(request: httpx.Request) -> dict:
    import json

    return json.loads(request.content.decode("utf-8"))
