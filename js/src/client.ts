import { makeNonce, signRequest, timestampSeconds } from "./auth.js";
import { NowDoingError, mapHttpError } from "./errors.js";
import type {
  ActivitySearchItem,
  BranchChangePayload,
  CurrentActivity,
  LogEntryRequest,
  LogEntryResult,
  NowDoingClientOptions,
  SearchActivitiesOptions,
  StartActivityRequest,
  StartActivityResult,
  Status,
} from "./types.js";

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 39847;
const DEFAULT_TIMEOUT_MS = 5000;

interface RequestEnvelope<T> {
  ok?: boolean;
  result?: T;
}

interface SearchResponse {
  items: ActivitySearchItem[];
}

export class NowDoingClient {
  private readonly token: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: NowDoingClientOptions = {}) {
    const rawToken = options.token ?? process.env.NOWDOING_TOKEN;
    const trimmed = (rawToken ?? "").trim();
    if (!trimmed) {
      throw new NowDoingError(
        "NowDoingClient: token is required (pass options.token or set NOWDOING_TOKEN).",
      );
    }
    this.token = trimmed;

    const envPort = (process.env.NOWDOING_PORT ?? "").trim();
    const port =
      options.port ??
      (envPort.length > 0 ? Number.parseInt(envPort, 10) : DEFAULT_PORT);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new NowDoingError(`NowDoingClient: invalid port ${port}.`);
    }
    const host = options.host ?? DEFAULT_HOST;
    this.baseUrl = `http://${host}:${port}`;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

    const candidate = options.fetch ?? globalThis.fetch;
    if (typeof candidate !== "function") {
      throw new NowDoingError(
        "NowDoingClient: no fetch implementation available (require Node ≥ 18 or pass options.fetch).",
      );
    }
    this.fetchImpl = candidate;
  }

  async healthcheck(): Promise<void> {
    await this.request<unknown>("GET", "/healthcheck");
  }

  async getCurrent(): Promise<CurrentActivity | null> {
    const data = await this.request<RequestEnvelope<CurrentActivity | null>>(
      "GET",
      "/current",
    );
    return data.result ?? null;
  }

  async searchActivities(
    query: string,
    options: SearchActivitiesOptions = {},
  ): Promise<ActivitySearchItem[]> {
    const params = new URLSearchParams();
    params.set("q", query);
    if (options.limit !== undefined) {
      params.set("limit", String(options.limit));
    }
    const data = await this.request<SearchResponse>(
      "GET",
      `/activities/search?${params.toString()}`,
    );
    return data.items ?? [];
  }

  async startActivity(
    request: StartActivityRequest,
  ): Promise<StartActivityResult> {
    if (!request.activityID && !request.name) {
      throw new NowDoingError(
        "startActivity: provide either activityID or name.",
      );
    }
    const body: Record<string, unknown> = {
      createIfMissing: request.createIfMissing ?? false,
    };
    if (request.activityID !== undefined) body.activityID = request.activityID;
    if (request.name !== undefined) body.name = request.name;

    const data = await this.request<RequestEnvelope<StartActivityResult>>(
      "POST",
      "/activities/start",
      body,
    );
    if (!data.result) {
      throw new NowDoingError("startActivity: missing result in response.");
    }
    return data.result;
  }

  async stopActivity(): Promise<void> {
    await this.request<unknown>("POST", "/activities/stop", {});
  }

  async getStatus(): Promise<Status> {
    const data = await this.request<RequestEnvelope<Status>>("GET", "/status");
    if (!data.result) {
      throw new NowDoingError("getStatus: missing result in response.");
    }
    return data.result;
  }

  async logEntry(request: LogEntryRequest): Promise<LogEntryResult> {
    if (!request.activityID && !request.name) {
      throw new NowDoingError("logEntry: provide either activityID or name.");
    }
    if (
      !Number.isInteger(request.durationMinutes) ||
      request.durationMinutes <= 0
    ) {
      throw new NowDoingError(
        "logEntry: durationMinutes must be a positive integer.",
      );
    }
    const body: Record<string, unknown> = {
      durationMinutes: request.durationMinutes,
      createIfMissing: request.createIfMissing ?? false,
    };
    if (request.activityID !== undefined) body.activityID = request.activityID;
    if (request.name !== undefined) body.name = request.name;
    if (request.note !== undefined) body.note = request.note;

    const data = await this.request<RequestEnvelope<LogEntryResult>>(
      "POST",
      "/entries",
      body,
    );
    if (!data.result) {
      throw new NowDoingError("logEntry: missing result in response.");
    }
    return data.result;
  }

  async notifyBranchChange(payload: BranchChangePayload): Promise<void> {
    if (!payload.branch || !payload.branch.trim()) {
      throw new NowDoingError("notifyBranchChange: branch is required.");
    }
    const body: Record<string, unknown> = { branch: payload.branch };
    if (payload.repo !== undefined) body.repo = payload.repo;
    if (payload.previousBranch !== undefined)
      body.previousBranch = payload.previousBranch;
    await this.request<unknown>("POST", "/branch-changed", body);
  }

  private async request<T>(
    method: string,
    target: string,
    body?: unknown,
  ): Promise<T> {
    const hasBody = body !== undefined;
    const bodyBytes = hasBody
      ? new TextEncoder().encode(JSON.stringify(body))
      : new Uint8Array();
    const timestamp = timestampSeconds();
    const nonce = makeNonce();
    const signature = signRequest({
      token: this.token,
      method,
      target,
      timestamp,
      nonce,
      body: bodyBytes,
    });

    const headers: Record<string, string> = {
      "X-NowDoing-Token": this.token,
      "X-NowDoing-Timestamp": timestamp,
      "X-NowDoing-Nonce": nonce,
      "X-NowDoing-Signature": signature,
    };
    if (hasBody) {
      headers["Content-Type"] = "application/json; charset=utf-8";
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${target}`, {
        method,
        headers,
        body: hasBody ? bodyBytes : undefined,
        signal: controller.signal,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : String(error ?? "unknown");
      throw new NowDoingError(`NowDoingClient: network error: ${message}`, {
        cause: error,
      });
    } finally {
      clearTimeout(timer);
    }

    const text = await response.text();
    let parsed: unknown = null;
    if (text.length > 0) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = null;
      }
    }

    if (!response.ok) {
      const serverMessage =
        (parsed && typeof parsed === "object" && "error" in parsed
          ? String((parsed as { error: unknown }).error)
          : undefined) ?? `HTTP ${response.status}`;
      throw mapHttpError(response.status, serverMessage);
    }
    return (parsed ?? {}) as T;
  }
}
