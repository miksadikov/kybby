export type ProjectSummary = {
  id: number
  slug: string
  name: string
  brand_id: string
  created_at: string
  updated_at: string
  results_url: string
  editor_url: string
}

export type ProjectsListResponse = {
  ok: boolean
  projects: ProjectSummary[]
  show_generation_history: boolean
}

export type CreateProjectResponse = {
  ok: boolean
  project: ProjectSummary
  redirect_url: string
}
