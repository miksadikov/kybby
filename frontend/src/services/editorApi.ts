import { apiClient } from './apiClient'
import type {
  PaletteRole,
  PaletteSuggestResponse,
  ProjectEditorRefsResponse,
  ProjectEditorResponse,
  ProjectEditorSaveResponse,
  ProjectTokens,
  StartGenerationPayload,
  StartGenerationResponse,
} from '../types/editor'

export function getProjectEditor(projectSlug: string, isNewProjectFlow = false): Promise<ProjectEditorResponse> {
  const query = isNewProjectFlow ? '?new=1' : ''
  return apiClient<ProjectEditorResponse>(`/api/projects/${projectSlug}/editor${query}`)
}

export function saveProjectEditor(projectSlug: string, tokens: ProjectTokens): Promise<ProjectEditorSaveResponse> {
  return apiClient<ProjectEditorSaveResponse>(`/api/projects/${projectSlug}/editor/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tokens),
  })
}

export function resetProjectEditor(projectSlug: string): Promise<ProjectEditorSaveResponse> {
  return apiClient<ProjectEditorSaveResponse>(`/api/projects/${projectSlug}/editor/reset`, { method: 'POST' })
}

export function listProjectEditorRefs(projectSlug: string): Promise<ProjectEditorRefsResponse> {
  return apiClient<ProjectEditorRefsResponse>(`/api/projects/${projectSlug}/editor/refs`)
}

export function uploadProjectEditorRefs(projectSlug: string, files: FileList | File[]): Promise<ProjectEditorRefsResponse> {
  const formData = new FormData()
  Array.from(files).forEach((file) => formData.append('files', file))

  return apiClient<ProjectEditorRefsResponse>(`/api/projects/${projectSlug}/editor/refs`, {
    method: 'POST',
    body: formData,
  })
}

export function deleteProjectEditorRef(projectSlug: string, path: string): Promise<ProjectEditorRefsResponse> {
  return apiClient<ProjectEditorRefsResponse>(`/api/projects/${projectSlug}/editor/refs/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
}

export function startProjectGeneration(projectSlug: string, payload: StartGenerationPayload): Promise<StartGenerationResponse> {
  return apiClient<StartGenerationResponse>(`/projects/${projectSlug}/generate/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function suggestProjectPalette(projectSlug: string, seedColor: string, seedRole: PaletteRole): Promise<PaletteSuggestResponse> {
  return apiClient<PaletteSuggestResponse>(`/projects/${projectSlug}/palette/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed_color: seedColor, seed_role: seedRole }),
  })
}
