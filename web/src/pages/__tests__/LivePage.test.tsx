import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { LivePage } from '../LivePage'

vi.mock('@/lib/api', () => ({
  tradingApi: {
    account: vi.fn().mockResolvedValue({
      nav: 1000000,
      cash: 500000,
      positions_count: 0,
      realized_pnl: 0,
      unrealized_pnl: 0,
      gross_exposure: 0,
      net_exposure: 0,
    }),
    orders: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    positions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    pnl: vi.fn().mockResolvedValue({ total_pnl: 0, return_pct: 0 }),
  },
  liveApi: {
    strategies: vi.fn().mockResolvedValue({ items: [] }),
    deployed: vi.fn().mockResolvedValue({ items: [] }),
    stopDeployed: vi.fn().mockResolvedValue({}),
    getExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  realtimeApi: {
    quote: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('@/hooks/useRealtimeQuote', () => ({
  useRealtimeQuote: () => ({ quotes: {}, connected: false }),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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

describe('LivePage', () => {
  it('renders page title', () => {
    renderWithProviders(<LivePage />)
    expect(screen.getByText('实盘监控')).toBeInTheDocument()
  })
})
