import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { BacktestsPage } from '../BacktestsPage'

// Mock ResizeObserver for recharts ResponsiveContainer
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.mock('@/lib/api', () => ({
  backtestsApi: {
    list: vi.fn().mockResolvedValue({
      items: [
        {
          run_id: 'run-abc-123',
          strategy_id: 'momentum_v1',
          status: 'completed',
          engine: 'vector',
          dataset_version: 'tdx_bulk_v1',
          started_at: '2026-01-01T10:00:00Z',
          completed_at: '2026-01-01T10:05:00Z',
          metrics: {
            total_return: 0.15,
            annualized_return: 0.18,
            sharpe_ratio: 1.2,
            max_drawdown: -0.08,
            win_rate: 0.55,
            total_trades: 120,
          },
        },
      ],
      total: 1,
    }),
    get: vi.fn().mockResolvedValue({
      run_id: 'run-abc-123',
      status: 'completed',
      metrics: { total_return: 0.15, sharpe_ratio: 1.2 },
      strategy_config: {
        market_rule: { market: 'CN', adj_type: 'forward' },
        rebalance_frequency: '1d',
        sizer: 'equal_weight',
      },
    }),
    getAnalysis: vi.fn().mockResolvedValue(null),
    getFills: vi.fn().mockResolvedValue({
      items: [
        {
          trade_date: '2025-06-01',
          asset_id: '000001.SZ',
          side: 'sell',
          qty: 1000,
          price: 12.5,
          notional: 12500,
          total_cost: 6.25,
          reason: 'delist_forced_liquidation',
          order_idx: 1,
        },
      ],
      total: 1,
    }),
    triggerAnalysis: vi.fn().mockResolvedValue({ job_id: 'j1', status: 'running' }),
    pollJob: vi.fn().mockResolvedValue({ status: 'completed', run_id: 'run-abc-123' }),
    getTca: vi.fn().mockResolvedValue({
      total_cost: 1234.56,
      cost_pct_turnover: 0.12,
      num_trades: 120,
      cost_per_trade: 10.29,
      total_commission: 800.0,
      total_stamp_duty: 234.56,
      total_slippage: 200.0,
    }),
    getAttribution: vi.fn().mockResolvedValue({
      active_return: 0.05,
      allocation_effect: 0.02,
      selection_effect: 0.025,
      interaction_effect: 0.005,
      sector_details: {
        '金融': { port_weight: 0.3, bench_weight: 0.25, port_return: 0.08, bench_return: 0.06 },
        '科技': { port_weight: 0.4, bench_weight: 0.35, port_return: 0.12, bench_return: 0.10 },
      },
    }),
    getRiskRolling: vi.fn().mockResolvedValue({
      run_id: 'run-abc-123',
      window: 60,
      data: [
        { trade_date: '2025-01-01', var_95: -0.02, cvar_95: -0.03, volatility: 0.15, sharpe_ratio: 1.1, drawdown: -0.01 },
        { trade_date: '2025-01-02', var_95: -0.025, cvar_95: -0.035, volatility: 0.16, sharpe_ratio: 1.05, drawdown: -0.015 },
      ],
    }),
    getDrawdowns: vi.fn().mockResolvedValue({
      run_id: 'run-abc-123',
      periods: [
        { period_id: 1, peak_date: '2025-01-15', trough_date: '2025-01-20', recovery_date: '2025-01-25', max_drawdown: -0.05, duration_days: 10 },
      ],
    }),
    getReturnDistribution: vi.fn().mockResolvedValue({
      run_id: 'run-abc-123',
      bins: 50,
      data: [
        { bin_start: -0.02, bin_end: -0.01, count: 5, bin_label: '-0.020' },
        { bin_start: -0.01, bin_end: 0.0, count: 10, bin_label: '-0.010' },
        { bin_start: 0.0, bin_end: 0.01, count: 15, bin_label: '0.000' },
      ],
      stats: { mean: 0.001, std: 0.015, skewness: -0.3, kurtosis: 3.2, min: -0.05, max: 0.04 },
    }),
  },
  backtestExtApi: {
    tearsheet: vi.fn().mockResolvedValue({ items: [] }),
    validationWindows: vi.fn().mockResolvedValue([]),
    multipleTesting: vi.fn().mockResolvedValue(null),
  },
  strategiesApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  liveApi: {
    strategies: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    positions: vi.fn().mockResolvedValue([]),
    risk: vi.fn().mockResolvedValue(null),
  },
}))

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('BacktestsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText('回测评估')).toBeInTheDocument()
    })
  })

  it('renders backtest run_id after loading', async () => {
    renderWithProviders(<BacktestsPage />)
    // run_id is truncated to first 8 chars + ellipsis in the table cell
    await waitFor(() => {
      expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
    })
  })

  it('renders record count in subtitle', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText(/1 条记录/)).toBeInTheDocument()
    })
  })

  it('shows parameter summary in overview tab', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText(/run-abc-/))
    await waitFor(() => {
      expect(screen.getByText(/市场:/)).toBeInTheDocument()
      expect(screen.getByText(/复权:/)).toBeInTheDocument()
    })
  })

  it('shows reason column and highlights delist rows in fills tab', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText(/run-abc-/))
    await waitFor(() => {
      fireEvent.click(screen.getByText('交易明细'))
    })
    await waitFor(() => {
      expect(screen.getByText('退市强制平仓')).toBeInTheDocument()
      expect(screen.getByText('原因')).toBeInTheDocument()
    })
  })

  it('shows TCA metrics when switching to tca tab', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText(/run-abc-/))
    await waitFor(() => {
      fireEvent.click(screen.getByText('成本分析'))
    })
    await waitFor(() => {
      expect(screen.getByText('总成本')).toBeInTheDocument()
      expect(screen.getByText('成本率')).toBeInTheDocument()
      expect(screen.getByText('交易笔数')).toBeInTheDocument()
      expect(screen.getByText('佣金')).toBeInTheDocument()
      expect(screen.getByText('印花税')).toBeInTheDocument()
      expect(screen.getByText('滑点')).toBeInTheDocument()
    })
  })

  it('shows Attribution metrics when switching to attribution tab', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => {
      expect(screen.getByText(/run-abc-/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText(/run-abc-/))
    await waitFor(() => {
      fireEvent.click(screen.getByText('归因分析'))
    })
    await waitFor(() => {
      expect(screen.getByText('超额收益')).toBeInTheDocument()
      expect(screen.getByText('配置效应')).toBeInTheDocument()
      expect(screen.getByText('选股效应')).toBeInTheDocument()
      expect(screen.getByText('交互效应')).toBeInTheDocument()
      expect(screen.getByText('行业归因明细')).toBeInTheDocument()
      expect(screen.getByText('金融')).toBeInTheDocument()
      expect(screen.getByText('科技')).toBeInTheDocument()
    })
  })

  it('shows risk analysis tab', async () => {
    renderWithProviders(<BacktestsPage />)
    await waitFor(() => { expect(screen.getByText(/run-abc-/)).toBeInTheDocument() })
    fireEvent.click(screen.getByText(/run-abc-/))
    await waitFor(() => { fireEvent.click(screen.getByText('风险分析')) })
    await waitFor(() => {
      expect(screen.getByText('滚动 VaR / CVaR')).toBeInTheDocument()
    })
  })
})
