import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { TradingPage } from '../TradingPage'

vi.mock('@/lib/api', () => ({
  tradingApi: {
    account: vi.fn().mockResolvedValue({
      nav: 1000000,
      cash: 500000,
      positions_count: 3,
      realized_pnl: 10000,
      unrealized_pnl: 5000,
      gross_exposure: 600000,
      net_exposure: 500000,
    }),
    orders: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    positions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    pnl: vi.fn().mockResolvedValue({ total_pnl: 0, return_pct: 0 }),
  },
  realtimeApi: {
    quote: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('@/hooks/useRealtimeQuote', () => ({
  useRealtimeQuote: () => ({ quotes: {}, connected: false }),
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

describe('TradingPage', () => {
  it('renders page title', () => {
    renderWithProviders(<TradingPage />)
    expect(screen.getByText('交易中心')).toBeInTheDocument()
  })
})
