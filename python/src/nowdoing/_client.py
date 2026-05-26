"""Synchronous NowDoing HTTP client."""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from ._base import (
    DEFAULT_TIMEOUT,
    build_branch_body,
    build_log_entry_body,
    build_request,
    build_search_target,
    build_start_body,
    handle_response,
    parse_current,
    parse_log_entry_result,
    parse_search,
    parse_start_result,
    parse_status,
    resolve_config,
)
from .errors import NowDoingError
from .models import (
    ActivitySearchItem,
    CurrentActivity,
    LogEntryResult,
    StartActivityResult,
    Status,
)


class NowDoingClient:
    """Synchronous client for the NowDoing loopback HTTP API.

    Example::

        with NowDoingClient(token="...") as client:
            client.healthcheck()
            current = client.get_current()
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        port: int | None = None,
        host: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._token, self._base_url = resolve_config(token=token, port=port, host=host)
        self._timeout = timeout
        self._owns_http = http_client is None
        self._http: httpx.Client = http_client or httpx.Client(timeout=timeout)

    def __enter__(self) -> "NowDoingClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    # ------------------------------------------------------------------ API

    def healthcheck(self) -> None:
        self._request("GET", "/healthcheck")

    def get_current(self) -> CurrentActivity | None:
        return parse_current(self._request("GET", "/current"))

    def search_activities(
        self,
        query: str = "",
        *,
        limit: int | None = None,
    ) -> list[ActivitySearchItem]:
        return parse_search(self._request("GET", build_search_target(query, limit)))

    def start_activity(
        self,
        *,
        activity_id: str | None = None,
        name: str | None = None,
        create_if_missing: bool = False,
    ) -> StartActivityResult:
        body = build_start_body(activity_id, name, create_if_missing)
        return parse_start_result(self._request("POST", "/activities/start", body))

    def stop_activity(self) -> None:
        self._request("POST", "/activities/stop", {})

    def get_status(self) -> Status:
        return parse_status(self._request("GET", "/status"))

    def log_entry(
        self,
        *,
        duration_minutes: int,
        activity_id: str | None = None,
        name: str | None = None,
        note: str | None = None,
        create_if_missing: bool = False,
    ) -> LogEntryResult:
        body = build_log_entry_body(
            activity_id, name, duration_minutes, note, create_if_missing,
        )
        return parse_log_entry_result(self._request("POST", "/entries", body))

    def notify_branch_change(
        self,
        *,
        branch: str,
        repo: str | None = None,
        previous_branch: str | None = None,
    ) -> None:
        body = build_branch_body(branch, repo, previous_branch)
        self._request("POST", "/branch-changed", body)

    # ------------------------------------------------------------- internal

    def _request(self, method: str, target: str, body: Any | None = None) -> Any:
        headers, body_bytes = build_request(
            token=self._token, method=method, target=target, body=body,
        )
        try:
            response = self._http.request(
                method=method,
                url=f"{self._base_url}{target}",
                headers=headers,
                content=body_bytes if body is not None else None,
            )
        except httpx.HTTPError as exc:
            raise NowDoingError(f"network error: {exc}") from exc
        return handle_response(response.status_code, response.text)
