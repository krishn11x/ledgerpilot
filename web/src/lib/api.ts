/**
 * Typed HTTP client.
 *
 * Thin on purpose. Types come from `src/api/generated.ts`, produced by
 * `npm run api:generate` against the live FastAPI OpenAPI schema -- so no
 * request or response interface is ever hand-written, and backend drift shows
 * up as a TypeScript error instead of a runtime surprise.
 */

/** Empty in dev so requests go through the Vite proxy at /api (no CORS). */
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const PREFIX = BASE ? BASE : "/api";
const AUTH_TOKEN = import.meta.env.VITE_API_AUTH_TOKEN ?? "local-demo-token";

/** Error envelope produced by `ledgerpilot.api.errors`. */
export interface ApiErrorBody {
  error: { code: string; message: string; detail?: unknown };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True while an endpoint is still scaffolded (HTTP 501). */
  get isNotImplemented() {
    return this.status === 501;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${AUTH_TOKEN}`,
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    let detail: unknown;
    try {
      const body = (await res.json()) as ApiErrorBody;
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
      detail = body.error?.detail;
    } catch {
      /* non-JSON error body; keep the status text */
    }
    throw new ApiError(res.status, code, message, detail);
  }

  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      // Spread rather than `body: undefined` -- exactOptionalPropertyTypes
      // distinguishes "absent" from "explicitly undefined".
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }),
};

/**
 * Subscribe to a run's progress stream.
 *
 * SSE rather than WebSockets: progress is unidirectional, so `EventSource`
 * handles reconnection for free and there is no protocol to design.
 *
 * TODO(phase-6): wire to the Exceptions page so breaks appear live.
 */
export function subscribeToRun(runId: string, onEvent: (e: MessageEvent) => void): () => void {
  const source = new EventSource(`${PREFIX}/runs/${runId}/events`);
  source.onmessage = onEvent;
  return () => source.close();
}
