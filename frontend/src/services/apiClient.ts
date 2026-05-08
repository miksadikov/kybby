export async function apiClient<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...init.headers,
    },
  })

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload) || `Request failed: ${response.status}`)
  }

  return payload as T
}

function extractErrorMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return ''
  if ('error' in payload && typeof payload.error === 'string') return payload.error
  if ('detail' in payload && typeof payload.detail === 'string') return payload.detail
  return ''
}
