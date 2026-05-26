"""Typed result objects returned by :class:`NowDoingClient`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentActivity:
    activity_id: str
    activity_name: str
    started_at: str  # ISO-8601, e.g. "2026-05-24T10:00:00Z"
    is_on_break: bool


@dataclass(frozen=True)
class ActivitySearchItem:
    id: str
    name: str
    group_name: str | None


@dataclass(frozen=True)
class StartActivityResult:
    activity_id: str
    activity_name: str
    created: bool


@dataclass(frozen=True)
class StatusActivity:
    activity_id: str
    activity_name: str


@dataclass(frozen=True)
class Status:
    is_tracking: bool
    is_on_break: bool
    current_activity: StatusActivity | None
    today_seconds: int


@dataclass(frozen=True)
class LogEntryResult:
    entry_id: str
    activity_id: str
    activity_name: str
    duration_minutes: int
    created: bool
