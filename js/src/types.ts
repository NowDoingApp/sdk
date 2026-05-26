export interface CurrentActivity {
  activityID: string;
  activityName: string;
  /** ISO-8601 timestamp, e.g. "2026-05-24T10:00:00Z". */
  startedAt: string;
  isOnBreak: boolean;
}

export interface ActivitySearchItem {
  id: string;
  name: string;
  groupName: string | null;
}

export interface StartActivityResult {
  activityID: string;
  activityName: string;
  created: boolean;
}

export interface StartActivityRequest {
  activityID?: string;
  name?: string;
  createIfMissing?: boolean;
}

export interface BranchChangePayload {
  branch: string;
  repo?: string | null;
  previousBranch?: string | null;
}

export interface SearchActivitiesOptions {
  limit?: number;
}

export interface StatusActivity {
  activityID: string;
  activityName: string;
}

export interface Status {
  isTracking: boolean;
  isOnBreak: boolean;
  currentActivity: StatusActivity | null;
  /** Tracked seconds across today, regardless of whether tracking is active right now. */
  todaySeconds: number;
}

export interface LogEntryRequest {
  activityID?: string;
  name?: string;
  durationMinutes: number;
  note?: string;
  createIfMissing?: boolean;
}

export interface LogEntryResult {
  entryID: string;
  activityID: string;
  activityName: string;
  durationMinutes: number;
  created: boolean;
}

export interface NowDoingClientOptions {
  /** Shared secret from NowDoing → Einstellungen → Integrationen. Falls back to `NOWDOING_TOKEN`. */
  token?: string;
  /** Loopback port the Mac app listens on. Falls back to `NOWDOING_PORT`, default 39847. */
  port?: number;
  /** Bind host. Defaults to `127.0.0.1`. */
  host?: string;
  /** Per-request timeout in milliseconds. Default 5000. */
  timeoutMs?: number;
  /** Injectable fetch implementation. Defaults to global `fetch`. */
  fetch?: typeof fetch;
}
