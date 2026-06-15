import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock ResizeObserver for recharts
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { RiskPage } from '../RiskPage'

const { mockRiskApi } = vi.hoisted(() => ({
  mockRiskApi: {
    policies: vi.fn().mockResolvedValue([
      {
        name: 'fixed_stop_loss',
        description: 'Fixed percentage stop loss',
        params: [{ key: 'stop_pct', type: 'float', default: -0.05, description: '止损比例' }],
      },
      {
        name: 'position_limit',
        description: 'Max position weight limit',
        params: [{ key: 'max_pct', type: 'float', default: 0.1, description: '最大仓位比例' }],
      },
    ]),
    sizers: vi.fn().mockResolvedValue([
      {
        name: 'equal_weight',
        description: 'Equal weight allocation',
        params: [],
      },
      {
        name: 'kelly',
        description: 'Kelly criterion sizing',
        params: [{ key: 'kelly_fraction', type: 'float', default: 0.5, description: 'Kelly 分数' }],
      },
    ]),
    check: vi.fn().mockResolvedValue({
      decision: 'approved',
      original_qty: 100,
      approved_qty: 100,
      reasons: [],
    }),
    getPositions: vi.fn().mockResolvedValue({
      positions: [],
      hhi: 0,
      max_weight: 0,
      sector_concentration: 0,
    }),
    getEvents: vi.fn().mockResolvedValue([
      { id: '1', severity: 'high', title: '集中度超限', description: 'HHI超过阈值', created_at: '2026-06-07T10:00:00Z' },
    ]),
  },
}))

vi.mock('@/lib/api', () => ({
  riskApi: mockRiskApi,
}))

vi.mock('@/lib/api/risk', () => ({
  riskApi: mockRiskApi,
}))

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RiskPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title', () => {
    renderWithProviders(<RiskPage />)
    expect(screen.getByText('风控管理')).toBeInTheDocument()
  })

  it('renders policies list after loading', async () => {
    renderWithProviders(<RiskPage />)
    await waitFor(() => {
      expect(screen.getAllByText('fixed_stop_loss').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('position_limit').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders sizers list after loading', async () => {
    renderWithProviders(<RiskPage />)
    await waitFor(() => {
      expect(screen.getAllByText('equal_weight').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('kelly').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders risk check tool', () => {
    renderWithProviders(<RiskPage />)
    expect(screen.getByText('风控检查工具')).toBeInTheDocument()
    expect(screen.getByText('执行风控检查')).toBeInTheDocument()
  })

  it('performs risk check and shows result', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RiskPage />)

    // Wait for policies to load
    await waitFor(() => {
      expect(screen.getAllByText('fixed_stop_loss').length).toBeGreaterThanOrEqual(1)
    })

    // Fill form
    await user.selectOptions(screen.getByDisplayValue('-- 选择策略 --'), 'fixed_stop_loss')
    await user.type(screen.getByPlaceholderText('600519.SSE'), '600519.SSE')

    // Run check
    await user.click(screen.getByText('执行风控检查'))

    await waitFor(() => {
      expect(screen.getByText('approved')).toBeInTheDocument()
    })
  })

  it('switches to position risk tab', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RiskPage />)
    await user.click(screen.getByText('持仓风控'))
    expect(screen.getByText('暂无持仓')).toBeInTheDocument()
  })

  it('switches to risk events tab', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RiskPage />)
    await user.click(screen.getByText('风控事件'))
    await waitFor(() => {
      expect(screen.getByText('集中度超限')).toBeInTheDocument()
    })
  })
})
