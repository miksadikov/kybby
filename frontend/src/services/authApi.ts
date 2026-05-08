import { apiClient } from './apiClient'
import type { AuthMeResponse, LoginPayload, RegisterPayload } from '../types/auth'

export function getCurrentSession(): Promise<AuthMeResponse> {
  return apiClient<AuthMeResponse>('/api/auth/me')
}

export function login(payload: LoginPayload): Promise<AuthMeResponse> {
  return apiClient<AuthMeResponse>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function register(payload: RegisterPayload): Promise<{ ok: boolean; error?: string }> {
  return apiClient<{ ok: boolean; error?: string }>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function logout(): Promise<AuthMeResponse> {
  return apiClient<AuthMeResponse>('/api/auth/logout', { method: 'POST' })
}
