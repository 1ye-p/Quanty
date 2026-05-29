/**
 * cQuant API client.
 * All functions throw on non-OK responses (TanStack Query will catch these).
 */

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const message = body.detail ?? body.message ?? `HTTP ${res.status}`
    const error = new Error(message)
    ;(error as Error & { status?: number }).status = res.status
    throw error
  }
  return res.json() as Promise<T>
}

// ── Datasets ──────────────────────────────────────────────────────────────────

export interface DatasetVersion {
  version_id: string
  dataset_name: string
  frequency: string
  start_date: string
  end_date: string
  asset_count: number | null
  row_count: number | null
  source: string
  created_at: string
  is_current: boolean
}

export const datasetsApi = {
  list: (limit = 50) =>
    request<{ items: DatasetVersion[]; total: number }>(`/datasets?limit=${limit}`),
  get: (id: string) => request<DatasetVersion>(`/datasets/${id}`),
  universes: () => request<{
    predefined: { id: string; name: string; description: string }[]
    available_assets: string[]
    total_assets: number
  }>('/datasets/universes'),
  quality: (version = '') =>
    request<{
      version: string
      stats: {
        n_assets: number
        min_date: string
        max_date: string
        total_rows: number
        recent_assets: number
        null_rate: number
        outlier_count: number
      }
      daily_coverage: { trade_date: string; n_assets: number }[]
      bottom_assets: { asset_id: string; valid_days: number }[]
    }>(`/datasets/quality?version=${encodeURIComponent(version)}`),

  scheduleStatus: () =>
    request<{
      enabled: boolean
      last_run: string | null
      last_status: 'success' | 'error' | 'running' | null
      last_error: string | null
      next_run: string | null
      last_data_date: string | null
    }>('/datasets/schedule'),

  triggerIngest: () =>
    request<{ status: string }>('/datasets/schedule/trigger', { method: 'POST' }),

  freshness: () =>
    request<{ last_updated: string | null; days_stale: number }>('/datasets/freshness'),
}

export const dashboardApi = {
  bestRecent: (days = 7) =>
    request<{
      run_id: string | null
      strategy_id: string | null
      sharpe: number | null
      max_drawdown: number | null
      cagr: number | null
    }>(`/backtests/best-recent?days=${days}`),

  icLeaderboard: (limit = 5) =>
    request<{
      items: { factor_name: string; mean_ic: number; ir: number; hit_rate: number }[]
    }>(`/factors/ic-leaderboard?limit=${limit}`),
}

// ── Walk-Forward Config ──────────────────────────────────────────────────────

export interface WalkForwardConfig {
  n_splits: number
  gap_days: number
  window_type: 'expanding' | 'sliding'
  step_days?: number
  purge_window: number
}

// ── Backtests ─────────────────────────────────────────────────────────────────

export interface BacktestRun {
  run_id: string
  engine: string
  strategy_id: string
  dataset_version: string
  started_at: string
  completed_at: string | null
  status: string
  is_running_job?: boolean
  metrics?: {
    total_return: number
    annualized_return: number
    annualized_volatility: number
    sharpe_ratio: number
    sortino_ratio: number
    max_drawdown: number
    calmar_ratio: number
    win_rate: number
    profit_factor: number
    var_95: number
    cvar_95: number
    beta: number | null
    total_trades: number
    trading_days: number
    information_ratio: number | null
    tracking_error: number | null
    alpha: number | null
    omega_ratio: number | null
    tail_ratio: number | null
    turnover_pct: number | null
    hhi: number | null
  }
}

export interface BacktestFill {
  trade_date: string
  asset_id: string
  side: string
  qty: number
  price: number
  notional: number
  commission: number
  stamp_duty: number
  slippage: number
  total_cost: number
}

export const backtestsApi = {
  list: (offset = 0, limit = 50) =>
    request<{ items: BacktestRun[]; total: number }>(`/backtests?offset=${offset}&limit=${limit}`),
  get: (id: string) => request<BacktestRun>(`/backtests/${id}`),
  getAnalysis: (id: string) => request<Record<string, unknown>>(`/backtests/${id}/analysis`),
  getRisk: (id: string, limit = 20) =>
    request<{ items: Record<string, unknown>[]; total: number }>(
      `/backtests/${id}/risk?limit=${limit}`,
    ),
  create: (body: {
    strategy_id: string
    dataset_version: string
    start_date: string
    end_date: string
    top_n?: number
    sort_factor?: string
    feature_set_version?: string
    strategy_type?: string
    model_version?: string
    label_name?: string
    train_end_date?: string
    walk_forward?: WalkForwardConfig
    eval_mode?: string
    // MarketNeutral
    short_n?: number
    // SectorRotation
    sector_map?: Record<string, string>
    top_sectors?: number
    top_n_per_sector?: number
    // Combo
    sub_strategy_configs?: Record<string, unknown>[]
    combo_method?: string
    // Universe
    universe_id?: string
    // Scoring integration
    scoring_run_id?: string
    // CustomWeightStrategy
    custom_weights?: Record<string, number>
    // Benchmark
    benchmark_asset_id?: string
  }) => request<{ job_id: string; strategy_id: string; status: string; warning?: string }>('/backtests', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  getFills: (id: string, limit = 200) =>
    request<{ items: BacktestFill[]; total: number }>(
      `/backtests/${id}/fills?limit=${limit}`,
    ),
  pollJob: (jobId: string) =>
    request<{ job_id: string; status: string; run_id: string | null; error: string | null }>(
      `/backtests/jobs/${jobId}`,
    ),
  triggerAnalysis: (id: string) =>
    request<{ job_id: string; run_id: string; status: string }>(
      `/backtests/${id}/analyze`,
      { method: 'POST' },
    ),
  compare: (runIds: string) =>
    request<{
      runs: Array<{
        run_id: string
        strategy_id: string
        engine: string
        status: string
        started_at: string
        dataset_version: string
        metrics: Record<string, number>
        nav_series: { date: string; nav: number }[]
      }>
    }>(`/backtests/compare?run_ids=${encodeURIComponent(runIds)}`),
  getWalkForwardFolds: (id: string) =>
    request<{
      run_id: string
      n_folds: number
      folds: Array<{
        fold_id: number
        train_start: string
        train_end: string
        test_start: string
        test_end: string
        fold_run_id: string
        metrics: Record<string, unknown>
      }>
      aggregated: Record<string, number>
    }>(`/backtests/${id}/walk-forward-folds`),
}

// ── Knowledge base ────────────────────────────────────────────────────────────

export interface KnowledgeDoc {
  doc_id: string
  title: string
  source_name: string
  logical_type: string
  language: string
  ingested_at: string
}

export interface SearchHit {
  doc_id: string
  title: string
  source_name: string
  logical_type: string
  score: number
  headline: string
}

export interface SearchResponse {
  hits: SearchHit[]
  total_found: number
  latency_ms: number
}

export const knowledgeApi = {
  list: (logicalType?: string, limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (logicalType) params.set('logical_type', logicalType)
    return request<{ items: KnowledgeDoc[]; total: number }>(`/knowledge/docs?${params}`)
  },
  get: (id: string) => request<KnowledgeDoc>(`/knowledge/docs/${id}`),
  search: (text: string, topK = 10) =>
    request<SearchResponse>('/knowledge/search', {
      method: 'POST',
      body: JSON.stringify({ text, top_k: topK }),
    }),
  ingest: (body: { uri: string; logical_type?: string; source_name?: string; title?: string }) =>
    request('/knowledge/ingest', { method: 'POST', body: JSON.stringify(body) }),
}

// ── AI Advisor ────────────────────────────────────────────────────────────────

export interface ChatResponse {
  response: string
  session_id: string
  artifacts: string[]
}

export const advisorApi = {
  chat: (message: string, sessionId?: string) =>
    request<ChatResponse>('/advisor/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId ?? '' }),
    }),
  report: (subject: string, sessionId?: string) =>
    request<{ report: string; session_id: string; artifacts: string[] }>('/advisor/report', {
      method: 'POST',
      body: JSON.stringify({ subject, session_id: sessionId ?? '' }),
    }),
}

// ── News ──────────────────────────────────────────────────────────────────────

export interface NewsEvent {
  event_id: string
  source: string
  headline: string
  published_at: string
  available_at: string
  asset_ids_mentioned: string[]
  sentiment_score: number | null
  event_type: string
  language: string
}

export interface NewsStats {
  total_events: number
  source_counts: Record<string, number>
  event_type_counts: Record<string, number>
  avg_sentiment: number | null
  daily_sentiment: { date: string; avg_sentiment: number; n_events: number }[]
}

export const newsApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params) : ''
    return request<{ items: NewsEvent[]; total: number }>(`/news/events${qs}`)
  },
  get: (id: string) => request<NewsEvent & { body?: string }>(`/news/events/${id}`),
  stats: () => request<NewsStats>('/news/stats'),
}

// ── Strategies ────────────────────────────────────────────────────────────────

export interface StrategyConfig {
  strategy_id: string
  config_format: string
  config_text: string
  parsed_config?: Record<string, unknown>
  universe_id?: string
  created_at: string
  updated_at: string
}

export const strategiesApi = {
  list: () => request<{ items: StrategyConfig[]; total: number }>('/strategies'),
  get: (id: string) => request<StrategyConfig>(`/strategies/${id}`),
  create: (body: { strategy_id: string; config_text: string; config_format?: string }) =>
    request('/strategies', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: { config_text: string; config_format?: string }) =>
    request(`/strategies/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: string) =>
    request(`/strategies/${id}`, { method: 'DELETE' }),

  versions: (strategyId: string) =>
    request<{
      items: Array<{
        version_id: string
        strategy_id: string
        config_text: string
        config_format: string
        summary: string
        created_at: string
      }>
      strategy_id: string
    }>(`/strategies/${strategyId}/versions`),

  rollback: (strategyId: string, versionId: string) =>
    request<{ strategy_id: string; status: string; version_id: string; summary: string }>(
      `/strategies/${strategyId}/rollback/${versionId}`,
      { method: 'POST' }
    ),
}

// ── ML ────────────────────────────────────────────────────────────────────────

export interface MLExperiment {
  run_id: string
  experiment_name?: string
  trainer_name: string
  status: string
  metrics: Record<string, number>
  params: Record<string, string>
  started_at?: string | number
  completed_at?: string | number
  artifact_uri?: string
  model_id?: string
  target_name?: string
  feature_set_version?: string
  error_text?: string
}

export interface MLJob {
  job_id: string
  trainer_name: string
  feature_set_version: string
  target_name: string
  status: string
  mlflow_run_id?: string
  submitted_at: string
  completed_at?: string
  error_text?: string
}

export const mlApi = {
  experiments: (limit = 50) =>
    request<{ items: MLExperiment[]; total: number; source: string }>(
      `/ml/experiments?limit=${limit}`,
    ),
  experiment: (id: string) => request<MLExperiment>(`/ml/experiments/${id}`),
  featureImportance: (id: string) =>
    request<{ items: { feature: string; importance: number }[]; total: number }>(
      `/ml/experiments/${id}/feature-importance`,
    ),
  submitJob: (body: {
    trainer: string
    feature_set_version: string
    target_name?: string
    params?: Record<string, unknown>
    walk_forward?: WalkForwardConfig
    train_ratio?: number
    valid_ratio?: number
  }) => request<{ job_id: string; status: string }>('/ml/jobs', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  jobStatus: (id: string) => request<MLJob>(`/ml/jobs/${id}`),
  predictions: (assetIds: string[]) =>
    request<{ date: string | null; predictions: Record<string, number> }>(
      `/ml/predictions?asset_ids=${encodeURIComponent(assetIds.join(','))}`,
    ),
}

// ── Live ──────────────────────────────────────────────────────────────────────

export interface LiveDeployment {
  live_id: string
  backtest_run_id: string
  strategy_id: string
  initial_cash: number
  risk_mode: string
  status: string
  deployed_at: string
  stopped_at: string | null
  metrics: { sharpe?: number | null; max_drawdown?: number | null; cagr?: number | null }
}

export interface LiveStrategy {
  strategy_id: string
  last_run_id: string
  last_update: string
  status: string
}

export const liveApi = {
  strategies: () => request<{ items: LiveStrategy[]; total: number; display_mode: string }>('/live/strategies'),
  pnl: (id: string, params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params) : ''
    return request<{ strategy_id: string; run_id: string; series: Record<string, unknown>[]; display_mode: string }>(
      `/live/strategies/${id}/pnl${qs}`,
    )
  },
  positions: (id: string) =>
    request<{ items: Record<string, unknown>[]; display_mode: string }>(`/live/strategies/${id}/positions`),
  risk: (id: string) =>
    request<{ latest_snapshot: Record<string, unknown> | null; history: Record<string, unknown>[]; display_mode: string }>(
      `/live/strategies/${id}/risk`,
    ),
  deploy: (body: { backtest_run_id: string; initial_cash: number; risk_mode: string }) =>
    request<{ live_id: string; strategy_id: string; status: string; deployed_at: string }>(
      '/live/deploy', { method: 'POST', body: JSON.stringify(body) }
    ),
  stopDeployed: (liveId: string) =>
    request<{ live_id: string; status: string }>(`/live/strategies/${liveId}/stop`, { method: 'POST' }),
  deployed: () =>
    request<{ items: LiveDeployment[] }>('/live/deployed'),
}

// ── Factors (extended) ────────────────────────────────────────────────────────

export interface FactorDefinition {
  name: string
  description: string
  tags: string[]
  source?: string
  factor_id?: string
  expression?: string
}
export interface ICPoint { trade_date: string; ic: number }
export interface ICJob {
  job_id: string
  status: string
  series_json?: ICPoint[]
  summary_json?: {
    mean_ic?: number
    ir?: number
    hit_rate?: number
    observations?: number
    rank_ic_decay?: { lag: number; ic: number }[]
    quantile_returns?: { quantile: number; mean_return: number }[]
    factor_turnover?: number
  }
}

export const factorAnalyticsApi = {
  definitions: () => request<{ items: FactorDefinition[]; total: number }>('/factors/definitions'),
  versions: () =>
    request<{ items: Array<{ feature_set_version: string; start_date: string; end_date: string; row_count: number }> }>(
      '/factors/versions',
    ),
  computeIC: (body: { factor_name: string; feature_set_version: string; horizon_days?: number }) =>
    request<{ job_id: string; status: string }>('/factors/analytics/compute', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  computeICMatrix: (body: { factor_names: string[]; feature_set_version: string; horizon_days?: number }) =>
    request<{ job_id: string; status: string }>('/factors/analytics/matrix', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  icJob: (jobId: string) => request<ICJob>(`/factors/analytics/${jobId}`),
  computeQuintiles: (body: {
    factor_name: string
    feature_set_version: string
    horizon_days?: number
    start_date?: string
    end_date?: string
    n_groups?: number
  }) =>
    request<{
      factor_name: string
      horizon_days: number
      n_groups: number
      groups: { quintile: string; mean_return: number; std_return: number; count: number }[]
    }>('/factors/analytics/quintiles', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  computeFactorCorrelation: (body: {
    factor_names: string[]
    feature_set_version: string
    start_date?: string
    end_date?: string
  }) =>
    request<{
      factors: string[]
      matrix: { factor_a: string; factor_b: string; correlation: number | null }[]
    }>('/factors/analytics/factor-correlation', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// ── Scoring ─────────────────────────────────────────────────────────────────

export interface ScoringRun {
  run_id: string
  config_name: string
  feature_set_version?: string
  start_date?: string
  end_date?: string
  status: string
  created_at?: string
  completed_at?: string
}

export interface ScoringResult {
  trade_date: string
  asset_id: string
  score: number | null
  rank: number | null
}

export interface ScoringConfigBody {
  name: string
  factors: { factor_name: string; weight: number; direction: string }[]
  feature_set_version: string
  start_date: string
  end_date: string
  winsorize?: number[]
  fill_null?: string
}

export const scoringApi = {
  run: (body: ScoringConfigBody) =>
    request<{ run_id: string; status: string }>('/scoring/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getResult: (runId: string, offset = 0, limit = 50, tradeDate = '') =>
    request<{
      run: ScoringRun
      results: ScoringResult[]
      total: number
      offset: number
      limit: number
      score_distribution: { breakpoint?: number; count: number }[]
      available_dates: string[]
    }>(`/scoring/results/${runId}?offset=${offset}&limit=${limit}${tradeDate ? `&trade_date=${tradeDate}` : ''}`),
  listSnapshots: (limit = 20) =>
    request<{ items: ScoringRun[] }>(`/scoring/snapshots?limit=${limit}`),
}

// ── Backtests (extended) ──────────────────────────────────────────────────────

export const backtestExtApi = {
  tearsheet: (id: string) => request<Record<string, unknown>>(`/backtests/${id}/tearsheet`),
  validationWindows: (id: string) =>
    request<{ walk_forward: Record<string, unknown>[]; cpcv: Record<string, unknown>[] }>(
      `/backtests/${id}/validation-windows`,
    ),
  multipleTesting: (id: string) =>
    request<Record<string, Record<string, unknown>>>(`/backtests/${id}/multiple-testing`),
}

// ── Advisor (extended) ────────────────────────────────────────────────────────

export const advisorExtApi = {
  session: (id: string) =>
    request<{ session_id: string; turn_count: number; history: Record<string, unknown>[] }>(
      `/advisor/sessions/${id}`,
    ),
  sessionAgents: (id: string) =>
    request<{ items: { agent_role: string; content: string; artifacts: string[] }[] }>(
      `/advisor/sessions/${id}/agents`,
    ),
  streamUrl: (message: string, sessionId?: string) => {
    const params = new URLSearchParams({ message })
    if (sessionId) params.set('session_id', sessionId)
    return `/api/v1/advisor/stream?${params}`
  },
}

// ── Portfolio Optimization ─────────────────────────────────────────────────────

export interface OptimizeRequest {
  expected_returns: Record<string, number>
  covariance: Record<string, Record<string, number>>
  optimizer?: 'mean_variance' | 'risk_parity' | 'cost_aware'
  constraints?: Record<string, unknown>
  risk_free_rate?: number
  long_only?: boolean
  cost_rate?: number
  turnover_penalty?: number
  current_weights?: Record<string, number>
}

export interface OptimizeResult {
  weights: Record<string, number>
  expected_return: number
  expected_volatility: number
  sharpe_ratio: number
  metadata: Record<string, unknown>
}

export interface CovarianceRequest {
  asset_ids: string[]
  as_of_date?: string
  method?: 'historical' | 'ewma' | 'ledoit_wolf'
  window?: number
  halflife?: number
}

export interface CovarianceResult {
  covariance: Record<string, Record<string, number>>
  assets: string[]
  method: string
  as_of_date: string
}

export const optimizeApi = {
  optimize: (body: OptimizeRequest) =>
    request<OptimizeResult>('/optimize', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  covariance: (body: CovarianceRequest) =>
    request<CovarianceResult>('/optimize/covariance', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// ── Risk Management ───────────────────────────────────────────────────────────

export interface PolicyParam {
  key: string
  type: string
  default: unknown
  description: string
}

export interface PolicyInfo {
  name: string
  description: string
  params: PolicyParam[]
}

export interface SizerInfo {
  name: string
  description: string
  params: PolicyParam[]
}

export interface RiskCheckRequest {
  policy_name: string
  params?: Record<string, unknown>
  asset_id: string
  side: string
  qty: number
  price: number
  nav?: number
  cash?: number
  positions?: Record<string, { qty?: number; avg_cost?: number; market_value?: number }>
  drawdown?: number
  as_of_date?: string
}

export interface RiskCheckResult {
  decision: 'approved' | 'clipped' | 'rejected'
  original_qty: number
  approved_qty: number
  reasons: string[]
}

export const riskApi = {
  policies: () => request<PolicyInfo[]>('/risk/policies'),
  sizers: () => request<SizerInfo[]>('/risk/sizers'),
  check: (body: RiskCheckRequest) =>
    request<RiskCheckResult>('/risk/check', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// ── Trading ───────────────────────────────────────────────────────────────────

export interface TradeOrder {
  order_id: string
  asset_id: string
  side: string
  qty: number
  order_type: string
  status: string
  filled_qty: number
  filled_price: number
  commission: number
  stamp_duty: number
  slippage: number
  total_cost: number
  reject_reason: string
  submitted_at: string | null
  filled_at: string | null
}

export interface TradePosition {
  asset_id: string
  qty: number
  avg_cost: number
  market_value: number
  unrealized_pnl: number
  realized_pnl: number
}

export interface TradeAccount {
  broker: string
  cash: number
  nav: number
  gross_exposure: number
  net_exposure: number
  realized_pnl: number
  unrealized_pnl: number
  positions_count: number
}

export interface TradePnL {
  broker: string
  nav: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  return_pct: number
}

export const tradingApi = {
  account: (broker = 'paper') =>
    request<TradeAccount>(`/trading/account?broker=${broker}`),

  placeOrder: (body: {
    asset_id: string
    side: string
    qty: number
    order_type?: string
    limit_price?: number
    broker?: string
  }) =>
    request<TradeOrder>('/trading/order', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  cancelOrder: (orderId: string, broker = 'paper') =>
    request<TradeOrder>(`/trading/order/${orderId}?broker=${broker}`, {
      method: 'DELETE',
    }),

  orders: (broker = 'paper', status?: string) => {
    const params = new URLSearchParams({ broker })
    if (status) params.set('status', status)
    return request<{ items: TradeOrder[]; total: number }>(`/trading/orders?${params}`)
  },

  positions: (broker = 'paper') =>
    request<{ items: TradePosition[]; total: number }>(`/trading/positions?broker=${broker}`),

  fills: (broker = 'paper') =>
    request<{ items: TradeOrder[]; total: number }>(`/trading/fills?broker=${broker}`),

  pnl: (broker = 'paper') =>
    request<TradePnL>(`/trading/pnl?broker=${broker}`),
}

// ── Real-time Quotes ──────────────────────────────────────────────────────────

export interface RealtimeQuote {
  asset_id: string
  symbol: string
  price: number
  open: number
  high: number
  low: number
  close: number
  prev_close: number
  volume: number
  amount: number
  bid1: number
  ask1: number
  bid1_vol: number
  ask1_vol: number
  change: number
  change_pct: number
  timestamp: string
}

export const realtimeApi = {
  quote: (symbol: string) =>
    request<RealtimeQuote>(`/live/quote/${symbol}`),

  quotes: (symbols: string[]) =>
    request<{ items: Record<string, RealtimeQuote>; count: number; timestamp: string }>(
      `/live/quotes?symbols=${symbols.join(',')}`,
    ),

  market: (limit = 20) =>
    request<{ items: Record<string, RealtimeQuote>; count: number; timestamp: string }>(
      `/live/market?limit=${limit}`,
    ),

  streamUrl: (symbols: string[], interval = 5) => {
    const params = new URLSearchParams({
      symbols: symbols.join(','),
      interval: String(interval),
    })
    return `/api/v1/live/stream?${params}`
  },
}

// ── Custom Factors ────────────────────────────────────────────────────────────

export interface CustomFactor {
  factor_id: string
  name: string
  expression: string
  description: string
  created_at: string
}

export const customFactorApi = {
  list: () =>
    request<{ items: CustomFactor[] }>('/factors/custom'),

  create: (body: { name: string; expression: string; description?: string }) =>
    request<{ factor_id: string; name: string; status: string }>(
      '/factors/custom', { method: 'POST', body: JSON.stringify(body) }
    ),

  delete: (factorId: string) =>
    request<{ factor_id: string; status: string }>(
      `/factors/custom/${factorId}`, { method: 'DELETE' }
    ),

  preview: (body: { expression: string; feature_set_version?: string }) =>
    request<{
      valid: boolean
      error: string | null
      preview: { asset_id: string; trade_date: string; value: number | null }[]
    }>('/factors/custom/preview', { method: 'POST', body: JSON.stringify(body) }),
}

export const alertsApi = {
  rules: () => request<{ items: AlertRule[]; rule_types: { type: string; label: string }[] }>('/alerts/rules'),
  createRule: (body: { rule_type: string; params: Record<string, unknown>; enabled?: boolean }) =>
    request<{ rule_id: string; status: string }>('/alerts/rules', { method: 'POST', body: JSON.stringify(body) }),
  deleteRule: (ruleId: string) =>
    request<{ rule_id: string; status: string }>(`/alerts/rules/${ruleId}`, { method: 'DELETE' }),
  history: (unreadOnly = false, limit = 50) =>
    request<{ items: AlertHistory[]; unread_count: number }>(
      `/alerts/history?unread_only=${unreadOnly}&limit=${limit}`
    ),
  markAllRead: () => request<{ status: string }>('/alerts/history/read-all', { method: 'POST' }),
  check: () => request<{ triggered: number }>('/alerts/check', { method: 'POST' }),
}

export interface AlertRule {
  rule_id: string
  rule_type: string
  rule_type_label: string
  params: Record<string, unknown>
  enabled: boolean
  created_at: string
}

export interface AlertHistory {
  alert_id: string
  rule_id: string
  rule_type: string
  message: string
  triggered_at: string
  read: boolean
}
