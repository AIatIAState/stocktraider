export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function fetchSymbols(query: string, limit = 25) {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return requestJson<{ results: SymbolInfo[] }>(`/api/symbols?${params.toString()}`)
}

export function fetchBars(params: {
  symbol: string
  timeframe: string
  start?: string
  end?: string
  limit?: number
  order?: 'asc' | 'desc'
}) {
  const qs = new URLSearchParams({
    symbol: params.symbol,
    timeframe: params.timeframe,
    ...(params.start ? { start: params.start } : {}),
    ...(params.end ? { end: params.end } : {}),
    ...(params.limit ? { limit: String(params.limit) } : {}),
    ...(params.order ? { order: params.order } : {}),
  })
  return requestJson<{ results: Bar[] }>(`/api/bars?${qs.toString()}`)
}

export function fetchWeeklyMovers(direction: 'top' | 'bottom') {
  const qs = new URLSearchParams({ direction })
  return requestJson<WeeklyMoversBatch>(`/api/weekly-movers?${qs.toString()}`)
}

export function fetchWeeklyInsights() {
  return requestJson<WeeklyInsightsResponse>('/api/weekly-insights')
}

export function refreshWeeklyInsights() {
  return requestJson<WeeklyInsightsResponse>('/api/admin/weekly-insights/refresh', {
    method: 'POST',
  })
}

export function fetchWeeklyAlerts() {
  return requestJson<WeeklyAlertsResponse>('/api/weekly-alerts')
}

export function runAdminUpdate(params: {
  start: string
  end: string
  symbols?: string[]
  limit?: number
}) {
  return requestJson<UpdateJob>('/api/admin/update', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export function fetchSchedulerStatus() {
  return requestJson<SchedulerStatus>('/api/admin/scheduler')
}

export function setSchedulerEnabled(enabled: boolean) {
  return requestJson<SchedulerStatus>('/api/admin/scheduler/enabled', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

export function fetchAdminUpdateStatus(jobId: string) {
  return requestJson<UpdateJob>(`/api/admin/update/${jobId}`)
}

export function fetchAdminUpdateJobs(status?: 'running' | 'completed' | 'failed') {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return requestJson<{ jobs: UpdateJob[] }>(`/api/admin/update/jobs${qs}`)
}

export function fetchDbInfo() {
  return requestJson<DbInfo>('/api/admin/db-info')
}

export type SymbolInfo = {
  symbol: string
  exchange: string | null
  asset_type: string | null
  country: string | null
}

export type Bar = {
  symbol: string
  per: string
  date: number
  time: number
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  openint: number | null
  timeframe: string
}

export type UpdateSummary = {
  symbols: number
  yf_symbols: number
  rows_fetched: number
  rows_inserted: number
}

export type UpdateJob = {
  id: string
  status: 'running' | 'completed' | 'failed'
  created_at: string
  started_at: string
  finished_at: string | null
  summary: UpdateSummary | null
  error: string | null
  start: string
  end: string
}

export type SchedulerStatus = {
  available: boolean
  enabled: boolean
  running: boolean
  timezone: string
  schedule: string
  next_run_time: string | null
  last_started_at: string | null
  last_finished_at: string | null
  last_status: 'running' | 'completed' | 'failed' | null
  last_job_id: string | null
  last_error: string | null
}

export type DbInfo = {
  db_path_env: string | null
  db_path: string
  db_path_resolved: string
  exists: boolean
  size_bytes: number | null
  mtime: string | null
  writable: boolean
  daily_min_date: string | null
  daily_max_date: string | null
  bootstrap_enabled: boolean
  bootstrap_start: string | null
  bootstrap_has_data: boolean | null
}

export type WeeklyMover = {
  symbol: string
  first_close: number
  last_close: number
  pct_change: number
  series?: number[]
}

export type MarketEvent = {
  title: string
  date: string | null
  source: string | null
  url?: string | null
  image_url?: string | null
}

export type WeeklyAlert = {
  symbol: string
  first_close: number
  last_close: number
  pct_change: number
  source: 'core' | 'top' | 'bottom'
}

export type WeeklyAlertFeatured = WeeklyAlert & {
  series: number[]
}

export type WeeklyInsightsResponse = {
  start: string
  end: string
  market_insights: string[]
  event_impacts: string[]
  events: MarketEvent[]
  note: string | null
  events_note: string | null
  model: string | null
  sources: string[]
}

export type WeeklyAlertsResponse = {
  start: string
  end: string
  alerts: WeeklyAlert[]
  featured: WeeklyAlertFeatured[]
}

export type WeeklyMoversBatch = {
  start: string
  end: string
  direction: 'top' | 'bottom'
  movers: WeeklyMover[]
}
