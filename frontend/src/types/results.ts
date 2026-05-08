export type ResultAsset = {
  provider: string
  name: string
  filename: string
  url: string
}

export type PaletteResultItem = {
  key: string
  label: string
  value: string
}

export type ProjectResultsResponse = {
  ok: boolean
  project: {
    slug: string
    name: string
    brand_id: string
  }
  palette_items: PaletteResultItem[]
  assets: {
    logos: ResultAsset[]
    icons: ResultAsset[]
    patterns: ResultAsset[]
    illustrations: ResultAsset[]
  }
  active_generation_job_id: string
  error?: string
}

export type FigmaExportResponse = {
  ok: boolean
  brand_id: string
  counts: Record<string, number>
  manifest_url: string
  download_url: string
  production_url: string
  local_url: string
  error?: string
}

export type GenerationJob = {
  id: string
  status: string
  progress: number
  message: string
  status_text?: string
  result_url?: string
  style_id?: string
  error?: string
  error_hint?: string
  logs?: string[]
  providers?: Record<string, string>
  provider_statuses?: Record<string, string>
}
