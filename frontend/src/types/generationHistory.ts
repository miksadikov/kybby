export type GenerationHistoryRow = {
  job_id: string
  started_display: string
  project_name: string
  project_slug: string
  status_key: 'success' | 'running' | 'error'
  duration_display: string
  action: 'cancel' | 'open' | 'restore' | 'repeat'
  results_url: string
  editor_url: string
  error_message: string
  error_hint: string
  interrupted: boolean
}

export type GenerationHistoryStats = {
  total: number
  successful: number
  avg_duration: number | null
  projects_with_generations: number
}

export type GenerationHistoryResponse = {
  ok: boolean
  rows: GenerationHistoryRow[]
  stats: GenerationHistoryStats
  stats_avg_display: string
  page: number
  per_page: number
  total: number
  total_pages: number
  has_prev: boolean
  has_next: boolean
  prev_page: number
  next_page: number
  showing_from: number
  showing_to: number
}
