import type { ProjectSummary } from './project'

export type ProjectTokens = Record<string, unknown>

export type ProjectEditorResponse = {
  ok: boolean
  project: ProjectSummary
  tokens: ProjectTokens
  refs: string[]
  is_new_project_flow: boolean
  error?: string
}

export type ProjectEditorSaveResponse = {
  ok: boolean
  tokens: ProjectTokens
  error?: string
}

export type ProjectEditorRefsResponse = {
  ok: boolean
  images: string[]
  error?: string
}

export type StartGenerationPayload = {
  style_id: string
  brand_id: string
  logos_count: number
  icons_count: number
  patterns_count: number
  illustrations_count: number
  build_style: boolean
}

export type StartGenerationResponse = {
  ok: boolean
  job_id: string
  error?: string
}

export type PaletteRole = 'primary' | 'secondary' | 'accent' | 'tertiary' | 'neutral' | 'extra'
export type PaletteVariantName = 'soft' | 'balanced' | 'contrast'

export type PaletteVariant = Record<PaletteRole, string>

export type PaletteSuggestResponse = {
  ok: boolean
  seed_color: string
  seed_role: PaletteRole
  variants: Record<PaletteVariantName, PaletteVariant>
  error?: string
}
