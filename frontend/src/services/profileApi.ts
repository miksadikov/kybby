import { apiClient } from './apiClient'
import type { ProfileResponse } from '../types/profile'

export function getProfile(): Promise<ProfileResponse> {
  return apiClient<ProfileResponse>('/api/profile')
}

export function updateProfile(formData: FormData): Promise<ProfileResponse> {
  return apiClient<ProfileResponse>('/api/profile/update', {
    method: 'POST',
    body: formData,
  })
}
