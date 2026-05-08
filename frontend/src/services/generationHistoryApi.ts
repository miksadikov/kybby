import { apiClient } from './apiClient'
import type { GenerationHistoryResponse } from '../types/generationHistory'

export function getGenerationHistory(page = 1): Promise<GenerationHistoryResponse> {
  return apiClient<GenerationHistoryResponse>(`/api/generation-history?page=${page}`)
}

export function deleteGenerationHistorySelected(jobIds: string[]): Promise<{ ok: boolean; deleted: number; skipped: number }> {
  return apiClient<{ ok: boolean; deleted: number; skipped: number }>('/api/generation-history/delete-selected', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_ids: jobIds }),
  })
}

export function cancelGenerationJob(jobId: string): Promise<{ ok: boolean; error?: string }> {
  return apiClient<{ ok: boolean; error?: string }>(`/generation-jobs/${jobId}/cancel`, { method: 'POST' })
}
