"""Shared request building + error mapping for sync and async clients."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

from ._auth import make_nonce, sign_request, timestamp_seconds
from .errors import NowDoingError, NowDoingHttpError, map_http_error
from .models import (
    ActivitySearchItem,
    CurrentActivity,
    LogEntryResult,
    StartActivityResult,
    Status,
    StatusActivity,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 39847
DEFAULT_TIMEOUT = 5.0


def resolve_config(
    *,
    token: str | None,
    port: int | None,
    host: str | None,
) -> tuple[str, str]:
    """Returns (token, base_url) or raises NowDoingError on misconfiguration."""
    resolved_token = (token or os.environ.get("NOWDOING_TOKEN") or "").strip()
    if not resolved_token:
        raise NowDoingError(
            "NowDoingClient: token is required (pass token= or set NOWDOING_TOKEN).",
        )

    if port is None:
        env_port = os.environ.get("NOWDOING_PORT", "").strip()
        resolved_port = int(env_port) if env_port else DEFAULT_PORT
    else:
        resolved_port = port
    if not (1 <= resolved_port <= 65535):
        raise NowDoingError(f"NowDoingClient: invalid port {resolved_port}.")

    resolved_host = host or DEFAULT_HOST
    return resolved_token, f"http://{resolved_host}:{resolved_port}"


def build_request(
    *,
    token: str,
    method: str,
    target: str,
    body: Any | None,
) -> tuple[dict[str, str], bytes]:
    """Returns (headers, body_bytes). body=None ⇒ empty body, no Content-Type header."""
    if body is None:
        body_bytes = b""
    else:
        body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")

    timestamp = timestamp_seconds()
    nonce = make_nonce()
    signature = sign_request(
        token=token,
        method=method,
        target=target,
        timestamp=timestamp,
        nonce=nonce,
        body=body_bytes,
    )
    headers = {
        "X-NowDoing-Token": token,
        "X-NowDoing-Timestamp": timestamp,
        "X-NowDoing-Nonce": nonce,
        "X-NowDoing-Signature": signature,
    }
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    return headers, body_bytes


def handle_response(status: int, text: str) -> Any:
    """Parse JSON, raise typed errors on 4xx/5xx, return parsed payload on 2xx."""
    payload: Any = None
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

    if status >= 400:
        message = "HTTP " + str(status)
        if isinstance(payload, dict) and isinstance(payload.get("error"), str):
            message = payload["error"]
        raise map_http_error(status, message)

    return payload if payload is not None else {}


def build_search_target(query: str, limit: int | None) -> str:
    params: dict[str, str] = {"q": query}
    if limit is not None:
        params["limit"] = str(limit)
    return "/activities/search?" + urlencode(params)


def parse_current(payload: Any) -> CurrentActivity | None:
    result = payload.get("result") if isinstance(payload, dict) else None
    if result is None:
        return None
    return CurrentActivity(
        activity_id=result["activityID"],
        activity_name=result["activityName"],
        started_at=result["startedAt"],
        is_on_break=bool(result["isOnBreak"]),
    )


def parse_search(payload: Any) -> list[ActivitySearchItem]:
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [
        ActivitySearchItem(
            id=item["id"],
            name=item["name"],
            group_name=item.get("groupName"),
        )
        for item in items
    ]


def parse_start_result(payload: Any) -> StartActivityResult:
    if not isinstance(payload, dict) or "result" not in payload:
        raise NowDoingHttpError(500, "missing result in /activities/start response")
    result = payload["result"]
    return StartActivityResult(
        activity_id=result["activityID"],
        activity_name=result["activityName"],
        created=bool(result["created"]),
    )


def build_start_body(
    activity_id: str | None,
    name: str | None,
    create_if_missing: bool,
) -> dict[str, Any]:
    if activity_id is None and name is None:
        raise NowDoingError("start_activity: provide either activity_id or name.")
    body: dict[str, Any] = {"createIfMissing": create_if_missing}
    if activity_id is not None:
        body["activityID"] = activity_id
    if name is not None:
        body["name"] = name
    return body


def parse_status(payload: Any) -> Status:
    if not isinstance(payload, dict) or "result" not in payload:
        raise NowDoingHttpError(500, "missing result in /status response")
    result = payload["result"]
    activity_payload = result.get("currentActivity")
    activity: StatusActivity | None
    if isinstance(activity_payload, dict):
        activity = StatusActivity(
            activity_id=activity_payload["activityID"],
            activity_name=activity_payload["activityName"],
        )
    else:
        activity = None
    return Status(
        is_tracking=bool(result["isTracking"]),
        is_on_break=bool(result["isOnBreak"]),
        current_activity=activity,
        today_seconds=int(result["todaySeconds"]),
    )


def parse_log_entry_result(payload: Any) -> LogEntryResult:
    if not isinstance(payload, dict) or "result" not in payload:
        raise NowDoingHttpError(500, "missing result in /entries response")
    result = payload["result"]
    return LogEntryResult(
        entry_id=result["entryID"],
        activity_id=result["activityID"],
        activity_name=result["activityName"],
        duration_minutes=int(result["durationMinutes"]),
        created=bool(result["created"]),
    )


def build_log_entry_body(
    activity_id: str | None,
    name: str | None,
    duration_minutes: int,
    note: str | None,
    create_if_missing: bool,
) -> dict[str, Any]:
    if activity_id is None and name is None:
        raise NowDoingError("log_entry: provide either activity_id or name.")
    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise NowDoingError("log_entry: duration_minutes must be a positive integer.")
    body: dict[str, Any] = {
        "durationMinutes": duration_minutes,
        "createIfMissing": create_if_missing,
    }
    if activity_id is not None:
        body["activityID"] = activity_id
    if name is not None:
        body["name"] = name
    if note is not None:
        body["note"] = note
    return body


def build_branch_body(
    branch: str,
    repo: str | None,
    previous_branch: str | None,
) -> dict[str, Any]:
    if not branch or not branch.strip():
        raise NowDoingError("notify_branch_change: branch is required.")
    body: dict[str, Any] = {"branch": branch}
    if repo is not None:
        body["repo"] = repo
    if previous_branch is not None:
        body["previousBranch"] = previous_branch
    return body
