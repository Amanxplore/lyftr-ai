import type {
  ChatRequestPayload,
  ChatResponsePayload,
  HealthResponsePayload,
  SessionMessagesResponsePayload,
} from '../types/chat';

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL as string | undefined;
  if (configured !== undefined && configured.trim() !== '') {
    return configured.trim().replace(/\/+$/, '');
  }
  // In production Docker behind nginx, /api can proxy or VITE_API_URL is set.
  // Default to http://localhost:8000 for local development.
  return 'http://localhost:8000';
}

export const API_BASE_URL = resolveApiBaseUrl();

export class ApiError extends Error {
  statusCode: number;
  detail: string;

  constructor(statusCode: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

function formatErrorDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') {
    return fallback;
  }
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const loc = Array.isArray((item as { loc?: unknown[] }).loc)
            ? (item as { loc: unknown[] }).loc.slice(1).join('.')
            : '';
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }
  return fallback;
}

export async function fetchHealth(): Promise<HealthResponsePayload> {
  const resp = await fetch(`${API_BASE_URL}/health`, {
    method: 'GET',
  });
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(
      resp.status,
      formatErrorDetail(data, `Health check failed (${resp.status})`)
    );
  }
  return data as HealthResponsePayload;
}

export async function sendChatMessage(
  payload: ChatRequestPayload,
  simulateFailureHeader?: string
): Promise<ChatResponsePayload> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (simulateFailureHeader && simulateFailureHeader.trim()) {
    headers['X-Simulate-Failure'] = simulateFailureHeader.trim();
  }

  const resp = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(
      resp.status,
      formatErrorDetail(data, `Request failed with status ${resp.status}`)
    );
  }
  return data as ChatResponsePayload;
}

export async function fetchSessionMessages(
  sessionId: string
): Promise<SessionMessagesResponsePayload> {
  const resp = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: 'GET',
    }
  );
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(
      resp.status,
      formatErrorDetail(data, `Failed to load session (${resp.status})`)
    );
  }
  return data as SessionMessagesResponsePayload;
}
