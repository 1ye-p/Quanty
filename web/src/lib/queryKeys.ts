/** TanStack Query key factories for consistent cache invalidation. */

export const queryKeys = {
  datasets: {
    all: ['datasets'] as const,
    list: (limit: number) => ['datasets', 'list', limit] as const,
    detail: (id: string) => ['datasets', id] as const,
  },
  backtests: {
    all: ['backtests'] as const,
    list: (offset: number, limit: number) => ['backtests', 'list', offset, limit] as const,
    detail: (id: string) => ['backtests', id] as const,
    analysis: (id: string) => ['backtests', id, 'analysis'] as const,
    risk: (id: string) => ['backtests', id, 'risk'] as const,
    tearsheet: (id: string) => ['backtests', id, 'tearsheet'] as const,
    validationWindows: (id: string) => ['backtests', id, 'validation-windows'] as const,
    multipleTesting: (id: string) => ['backtests', id, 'multiple-testing'] as const,
    fills: (id: string, offset: number, limit: number) => ['backtests', id, 'fills', offset, limit] as const,
    walkForward: (id: string) => ['backtests', id, 'walk-forward-folds'] as const,
    tca: (id: string) => ['backtests', id, 'tca'] as const,
    attribution: (id: string) => ['backtests', id, 'attribution'] as const,
    riskRolling: (id: string, window: number) => ['backtests', id, 'risk-rolling', window] as const,
    drawdowns: (id: string) => ['backtests', id, 'drawdowns'] as const,
    drawdownTimeseries: (id: string) => ['backtests', id, 'drawdown-timeseries'] as const,
    returnDistribution: (id: string) => ['backtests', id, 'return-distribution'] as const,
    correlation: (id: string) => ['backtests', id, 'correlation'] as const,
    factorExposure: (id: string) => ['backtests', id, 'factor-exposure'] as const,
    stressTest: (id: string) => ['backtests', id, 'stress-test'] as const,
    riskContribution: (id: string) => ['backtests', id, 'risk-contribution'] as const,
  },
  knowledge: {
    all: ['knowledge'] as const,
    list: (type?: string) => ['knowledge', 'list', type] as const,
    detail: (id: string) => ['knowledge', id] as const,
    search: (text: string) => ['knowledge', 'search', text] as const,
  },
} as const

export const extendedQueryKeys = {
  news: {
    list: (params?: Record<string, string>) => ['news', 'list', params] as const,
    detail: (id: string) => ['news', id] as const,
    stats: () => ['news', 'stats'] as const,
  },
  strategies: {
    all: ['strategies'] as const,
    list: () => ['strategies', 'list'] as const,
    detail: (id: string) => ['strategies', id] as const,
  },
  ml: {
    experiments: (limit: number) => ['ml', 'experiments', limit] as const,
    experiment: (id: string) => ['ml', 'experiment', id] as const,
    featureImportance: (id: string) => ['ml', 'fi', id] as const,
    job: (id: string) => ['ml', 'job', id] as const,
    predict: (id: string) => ['ml', 'predict', id] as const,
  },
  live: {
    strategies: () => ['live', 'strategies'] as const,
    pnl: (id: string) => ['live', 'pnl', id] as const,
    positions: (id: string) => ['live', 'positions', id] as const,
    risk: (id: string) => ['live', 'risk', id] as const,
  },
  factorAnalytics: {
    definitions: () => ['factors', 'definitions'] as const,
    icJob: (id: string) => ['factors', 'ic', id] as const,
  },
  dsl: {
    functions: ['factors', 'dsl', 'functions'] as const,
  },
  trading: {
    account: (broker: string) => ['trading', 'account', broker] as const,
    orders: (broker: string, status?: string) => ['trading', 'orders', broker, status] as const,
    positions: (broker: string) => ['trading', 'positions', broker] as const,
    fills: (broker: string) => ['trading', 'fills', broker] as const,
    pnl: (broker: string) => ['trading', 'pnl', broker] as const,
  },
  realtime: {
    quote: (symbol: string) => ['realtime', 'quote', symbol] as const,
    quotes: (symbols: string[]) => ['realtime', 'quotes', ...symbols] as const,
    market: (limit: number) => ['realtime', 'market', limit] as const,
  },
  risk: {
    policies: () => ['risk', 'policies'] as const,
    sizers: () => ['risk', 'sizers'] as const,
  },
} as const
