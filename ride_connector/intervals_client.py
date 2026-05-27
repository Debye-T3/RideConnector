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

    @staticmethod
    def _retry(send: Callable[[], httpx.Response], attempts: int = 3) -> Any:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                response = send()
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Intervals API request failed after {attempts} attempts") from last_error

