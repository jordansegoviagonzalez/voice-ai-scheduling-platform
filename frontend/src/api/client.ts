export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequestAbsolute<T>(`${API_BASE}${path}`, init);
}

export async function apiRequestAbsolute<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  const payload = (await response.json().catch(() => null)) as
    | T
    | { error?: { code?: string; message?: string } }
    | null;
  if (!response.ok) {
    const errorPayload = payload as { error?: { code?: string; message?: string } } | null;
    throw new ApiClientError(
      errorPayload?.error?.message ?? 'The request could not be completed.',
      response.status,
      errorPayload?.error?.code,
    );
  }
  return payload as T;
}
