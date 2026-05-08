import { apiClient } from './apiClient'
import type { FigmaExportResponse, GenerationJob, ProjectResultsResponse } from '../types/results'

export function getProjectResults(projectSlug: string): Promise<ProjectResultsResponse> {
  return apiClient<ProjectResultsResponse>(`/api/projects/${projectSlug}/results`)
}

export function generateFigmaManifest(projectSlug: string, brandId: string): Promise<FigmaExportResponse> {
  return apiClient<FigmaExportResponse>(`/projects/${projectSlug}/generate-figma`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brandId ? { brand_id: brandId } : {}),
  })
}

export function getActiveGenerationJob(projectSlug: string): Promise<{ ok: boolean; job: GenerationJob | null }> {
  return apiClient<{ ok: boolean; job: GenerationJob | null }>(`/projects/${projectSlug}/generation/active`)
}

export function getGenerationJob(jobId: string): Promise<{ ok: boolean; job: GenerationJob }> {
  return apiClient<{ ok: boolean; job: GenerationJob }>(`/generation-jobs/${jobId}`)
}

export function cancelGenerationJob(jobId: string): Promise<{ ok: boolean; error?: string }> {
  return apiClient<{ ok: boolean; error?: string }>(`/generation-jobs/${jobId}/cancel`, { method: 'POST' })
}
