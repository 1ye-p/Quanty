import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { RiskPage } from '../RiskPage'

vi.mock('@/lib/api', () => ({
  riskApi: {
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
  },
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
})
