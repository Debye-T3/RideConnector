from __future__ import annotations

from datetime import date
from typing import Any, Callable, TypeVar

import httpx

from ride_connector.models import TrainingEvent, WellnessEntry

T = TypeVar("T")


class IntervalsClient:
    def __init__(
        self,
        api_key: str,
        athlete_id: str = "0",
        base_url: str = "https://intervals.icu/api/v1",
        client: httpx.Client | None = None,
    ) -> None:
        self.athlete_id = athlete_id
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=httpx.BasicAuth("API_KEY", api_key),
            timeout=20,
        )

    def get_events(self, oldest: date, newest: date) -> list[TrainingEvent]:
        data = self._retry(
            lambda: self._client.get(
                f"/athlete/{self.athlete_id}/events",
                params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            )
        )
        items = data if isinstance(data, list) else data.get("events", [])
        return [TrainingEvent.from_api(item) for item in items if isinstance(item, dict)]

    def get_wellness(self, oldest: date, newest: date) -> list[WellnessEntry]:
        data = self._retry(
            lambda: self._client.get(
                f"/athlete/{self.athlete_id}/wellness",
                params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            )
        )
        items = data if isinstance(data, list) else data.get("wellness", [])
        return [WellnessEntry.from_api(item) for item in items if isinstance(item, dict)]

    def update_wellness(self, entry_date: date, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._retry(
            lambda: self._client.put(
                f"/athlete/{self.athlete_id}/wellness/{entry_date.isoformat()}",
                json=payload,
            )
        )
        return data if isinstance(data, dict) else {"result": data}

    def update_wellness_weight(self, entry_date: date, weight_kg: float) -> dict[str, Any]:
        existing_entries = self.get_wellness(entry_date, entry_date)
        existing = dict(existing_entries[0].raw) if existing_entries else {"id": entry_date.isoformat()}
        existing["weight"] = weight_kg
        return self.update_wellness(entry_date, existing)

    @staticmethod
    def _retry(send: Callable[[], httpx.Response], attempts: int = 3) -> Any:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                response = send()
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Intervals API request failed after {attempts} attempts") from last_error
