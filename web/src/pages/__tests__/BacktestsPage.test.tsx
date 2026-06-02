import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { BacktestsPage } from '../BacktestsPage'

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
})
