from __future__ import annotations

from typing import Any

import httpx


class GitHubClient:
    def __init__(
        self,
        repository: str,
        token: str,
        api_url: str = "https://api.github.com",
        client: httpx.Client | None = None,
    ) -> None:
        if not repository:
            raise ValueError("GITHUB_REPOSITORY is required")
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self._client = client or httpx.Client(
            timeout=20,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def get_issue(self, issue_number: int) -> dict[str, Any]:
        response = self._client.get(f"{self.api_url}/repos/{self.repository}/issues/{issue_number}")
        response.raise_for_status()
        return response.json()

    def comment_issue(self, issue_number: int, body: str) -> None:
        response = self._client.post(
            f"{self.api_url}/repos/{self.repository}/issues/{issue_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()

    def close_issue(self, issue_number: int) -> None:
        response = self._client.patch(
            f"{self.api_url}/repos/{self.repository}/issues/{issue_number}",
            json={"state": "closed", "state_reason": "completed"},
        )
        response.raise_for_status()
