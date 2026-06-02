import { Page, expect } from '@playwright/test'

/** Mock API responses for E2E tests — avoids dependency on running backend. */
export async function mockAllApis(page: Page) {
  // Health
  await page.route('**/api/v1/health**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok' }) }),
  )

  // Datasets
  await page.route('**/api/v1/datasets**', route => {
    const url = route.request().url()
    if (url.includes('/freshness')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        total_assets: 6675, latest_date: '2026-05-30', days_behind: 1,
      })})
    }
    if (url.includes('/universes')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        predefined: [{ id: 'all', name: '全市场', description: '全部A股' }],
        available_assets: ['SSE:600000', 'SZSE:000001'],
        total_assets: 6675,
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({
      items: [{
        version_id: 'tdx_bulk_v1', source: 'tdx', start_date: '2024-01-01',
        end_date: '2026-05-30', row_count: 3_200_000, created_at: '2026-05-17',
      }],
      total: 1,
    })})
  })

  // Backtests
  await page.route('**/api/v1/backtests**', route => {
    const url = route.request().url()
    const method = route.request().method()
    if (url.includes('/best-recent')) {
      return route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) })
    }
    if (method === 'POST') {
      return route.fulfill({ status: 201, body: JSON.stringify({
        run_id: 'bt-e2e-001', status: 'running', job_id: 'job-bt-001',
      })})
    }
    if (url.includes('/jobs/')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        job_id: 'job-bt-001', status: 'done',
        result: {
          run_id: 'bt-e2e-001', strategy_id: 'top10_equal', status: 'completed',
          start_date: '2025-01-01', end_date: '2025-06-30',
          total_return: 0.156, annual_return: 0.312, sharpe_ratio: 1.85,
          max_drawdown: -0.082, win_rate: 0.58, total_trades: 120,
          nav_series: [
            { date: '2025-01-01', nav: 1.0 },
            { date: '2025-03-01', nav: 1.08 },
            { date: '2025-06-30', nav: 1.156 },
          ],
        },
      })})
    }
    if (url.includes('/bt-e2e-001') && !url.includes('/risk') && !url.includes('/fills')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        run_id: 'bt-e2e-001', strategy_id: 'top10_equal', status: 'completed',
        start_date: '2025-01-01', end_date: '2025-06-30',
        metrics: {
          total_return: 0.156, annualized_return: 0.312, sharpe_ratio: 1.85,
          max_drawdown: -0.082, win_rate: 0.58, total_trades: 120,
          calmar_ratio: 3.8, sortino_ratio: 2.4, information_ratio: 1.2,
          turnover: 0.35,
        },
        nav_series: [
          { date: '2025-01-01', nav: 1.0 },
          { date: '2025-03-01', nav: 1.08 },
          { date: '2025-06-30', nav: 1.156 },
        ],
      })})
    }
    if (url.includes('/risk')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        var_95: -0.018, cvar_95: -0.025, beta: 0.85, volatility: 0.16,
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({
      items: [{
        run_id: 'bt-e2e-001', strategy_id: 'top10_equal', status: 'completed',
        engine: 'vectorbt', started_at: '2025-01-01T00:00:00Z', completed_at: '2025-06-30T00:00:00Z',
      }],
      total: 1,
    })})
  })

  // Strategies
  await page.route('**/api/v1/strategies**', route => {
    const method = route.request().method()
    if (method === 'POST') {
      return route.fulfill({ status: 201, body: JSON.stringify({
        strategy_id: 'e2e_strategy', status: 'created',
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({
      items: [{
        strategy_id: 'top10_equal',
        config_format: 'json',
        config_text: JSON.stringify({ strategy_type: 'StaticTopN', factors: ['ret_20d', 'vol_20d'], top_n: 10 }),
        parsed_config: { strategy_type: 'StaticTopN', factors: ['ret_20d', 'vol_20d'], top_n: 10 },
        created_at: '2026-05-20',
        updated_at: '2026-05-20',
      }],
      total: 1,
    })})
  })

  // Factors
  await page.route('**/api/v1/factors**', route => {
    const url = route.request().url()
    if (url.includes('/definitions')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [
          { name: 'ret_5d', description: '5日收益率', tags: ['momentum'], source: 'builtin' },
          { name: 'ret_20d', description: '20日收益率', tags: ['momentum'], source: 'builtin' },
          { name: 'vol_20d', description: '20日波动率', tags: ['risk'], source: 'builtin' },
          { name: 'ma_5', description: '5日均线', tags: ['trend'], source: 'builtin' },
          { name: 'rsi_14', description: '14日RSI', tags: ['momentum'], source: 'builtin' },
        ],
        total: 5,
      })})
    }
    if (url.includes('/versions')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [{
          feature_set_version: 'v1_20260101', start_date: '2024-01-01',
          end_date: '2026-01-01', row_count: 100000,
        }],
      })})
    }
    if (url.includes('/ic-status')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [
          { factor_name: 'ret_5d', mean_ic: 0.05, ir: 0.8, hit_rate: 0.55, is_alert: false },
          { factor_name: 'ret_20d', mean_ic: 0.008, ir: 0.1, hit_rate: 0.48, is_alert: true, alert_message: 'IC 0.008 低于阈值 0.02' },
          { factor_name: 'vol_20d', mean_ic: 0.03, ir: 0.6, hit_rate: 0.52, is_alert: false },
        ],
        threshold: 0.02, window_days: 20, feature_set_version: 'v1_20260101',
      })})
    }
    if (url.includes('/ic-leaderboard')) {
      return route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) })
    }
    if (url.includes('/analytics/compute')) {
      return route.fulfill({ status: 202, body: JSON.stringify({ job_id: 'ic-job-1', status: 'running' }) })
    }
    if (url.includes('/analytics/')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        job_id: 'ic-job-1', status: 'done',
        series_json: [
          { trade_date: '2026-01-01', ic: 0.05 },
          { trade_date: '2026-01-02', ic: 0.03 },
        ],
        summary_json: { mean_ic: 0.04, ir: 0.7, hit_rate: 0.55, observations: 200 },
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({
      items: [
        { name: 'ret_5d', description: '5日收益率', tags: ['momentum'], source: 'builtin' },
        { name: 'vol_20d', description: '20日波动率', tags: ['risk'], source: 'builtin' },
      ],
      total: 2,
    })})
  })

  // Custom factors
  await page.route('**/api/v1/factors/custom**', route => {
    const method = route.request().method()
    if (method === 'POST') {
      const url = route.request().url()
      if (url.includes('/preview')) {
        return route.fulfill({ status: 200, body: JSON.stringify({
          valid: true, error: null,
          preview: [{ asset_id: 'SSE:600000', trade_date: '2026-01-01', value: 1.23 }],
        })})
      }
      return route.fulfill({ status: 201, body: JSON.stringify({ factor_id: 'cf1', status: 'created' }) })
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) })
  })

  // ML
  await page.route('**/api/v1/ml**', route => {
    const url = route.request().url()
    const method = route.request().method()
    if (url.includes('/experiments') && !url.includes('/feature-importance')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [{
          run_id: 'ml-run-001', trainer_name: 'LightGBM', status: 'completed',
          metrics: { sharpe: 1.2, accuracy: 0.62 }, created_at: '2026-05-28',
        }],
        total: 1,
      })})
    }
    if (url.includes('/feature-importance')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        features: [
          { name: 'ret_20d', importance: 0.35 },
          { name: 'vol_20d', importance: 0.25 },
          { name: 'ma_5', importance: 0.20 },
        ],
      })})
    }
    if (method === 'POST' && url.includes('/jobs')) {
      return route.fulfill({ status: 202, body: JSON.stringify({ job_id: 'ml-job-1', status: 'running' }) })
    }
    if (url.includes('/jobs/')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        job_id: 'ml-job-1', status: 'done',
        result: { run_id: 'ml-run-001', metrics: { sharpe: 1.2 } },
      })})
    }
    if (url.includes('/predictions')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        date: '2026-01-15', predictions: { 'SSE:600000': 0.08, 'SZSE:000001': 0.05 },
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) })
  })

  // Optimize
  await page.route('**/api/v1/optimize**', route => {
    const url = route.request().url()
    if (url.endsWith('/optimize') || url.includes('/optimize?')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        weights: { 'SSE:600000': 0.6, 'SZSE:000001': 0.4 },
        expected_return: 0.12, expected_volatility: 0.18, sharpe_ratio: 0.667,
        metadata: { turnover: 0.15 },
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({
      covariance: { 'SSE:600000': { 'SSE:600000': 0.04, 'SZSE:000001': 0.01 }, 'SZSE:000001': { 'SSE:600000': 0.01, 'SZSE:000001': 0.09 } },
      assets: ['SSE:600000', 'SZSE:000001'], method: 'historical', as_of_date: '2026-01-01',
    })})
  })

  // Alerts
  await page.route('**/api/v1/alerts**', route => {
    const url = route.request().url()
    const method = route.request().method()
    if (url.includes('/rules') && method === 'GET') {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [{
          rule_id: 'r1', rule_type: 'data_stale', rule_type_label: '数据过期',
          params: { max_days: 2 }, enabled: true, created_at: '2026-01-01',
        }],
        rule_types: [
          { type: 'data_stale', label: '数据过期' },
          { type: 'factor_ic_low', label: '因子 IC 低' },
        ],
      })})
    }
    if (url.includes('/rules') && method === 'POST') {
      return route.fulfill({ status: 201, body: JSON.stringify({ rule_id: 'r2', status: 'created' }) })
    }
    if (url.includes('/history') && method === 'GET') {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [
          { alert_id: 'a1', rule_type: 'data_stale', message: '数据已过期 3 天', triggered_at: '2026-01-15T10:30:00Z', read: false },
        ],
        unread_count: 1,
      })})
    }
    if (url.includes('/check')) {
      return route.fulfill({ status: 200, body: JSON.stringify({ triggered: 1 }) })
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok' }) })
  })

  // Risk
  await page.route('**/api/v1/risk**', route => {
    const url = route.request().url()
    if (url.includes('/policies')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [
          { id: 'position_limit', name: '仓位限制', description: '单只最大仓位', params: [{ name: 'max_pct', type: 'number', default: 0.10 }] },
          { id: 'stop_loss', name: '止损', description: '个股止损', params: [{ name: 'stop_loss_pct', type: 'number', default: 0.05 }] },
        ],
      })})
    }
    if (url.includes('/sizers')) {
      return route.fulfill({ status: 200, body: JSON.stringify({
        items: [
          { id: 'equal_weight', name: '等权', description: '等权分配' },
          { id: 'risk_parity', name: '风险平价', description: '风险平价分配' },
        ],
      })})
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ passed: true, violations: [] }) })
  })

  // Scoring
  await page.route('**/api/v1/scoring**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) }),
  )

  // Live
  await page.route('**/api/v1/live**', route => {
    const url = route.request().url()
    if (url.includes('/deployed')) {
      return route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) })
    }
    if (url.includes('/strategies')) {
      return route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) })
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) })
  })

  // News
  await page.route('**/api/v1/news**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) }),
  )

  // Knowledge
  await page.route('**/api/v1/knowledge**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) }),
  )

  // Advisor
  await page.route('**/api/v1/advisor**', route => {
    const url = route.request().url()
    if (url.includes('/sessions') && route.request().method() === 'GET') {
      return route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) })
    }
    return route.fulfill({ status: 200, body: JSON.stringify({ response: '分析完成', session_id: 's1' }) })
  })

  // Plugins
  await page.route('**/api/v1/plugins**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) }),
  )

  // Trading
  await page.route('**/api/v1/trading**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [], total: 0 }) }),
  )

  // Dashboard
  await page.route('**/api/v1/dashboard**', route =>
    route.fulfill({ status: 200, body: JSON.stringify({ items: [] }) }),
  )
}

/** Navigate to a page and wait for it to be idle (no pending network). */
export async function gotoPage(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
}
