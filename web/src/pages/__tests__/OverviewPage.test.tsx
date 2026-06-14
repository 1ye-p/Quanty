import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { OverviewPage } from '../OverviewPage'

vi.mock('@/lib/api', () => ({
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    freshness: vi.fn().mockResolvedValue({ last_updated: null, days_stale: -1 }),
  },
  backtestsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  knowledgeApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  liveApi: {
    strategies: vi.fn().mockResolvedValue({ items: [] }),
  },
  dashboardApi: {
    bestRecent: vi.fn().mockResolvedValue(null),
    icLeaderboard: vi.fn().mockResolvedValue({ items: [] }),
    backtestTrend: vi.fn().mockResolvedValue({ items: [] }),
    icTrend: vi.fn().mockResolvedValue({ items: [] }),
  },
  realtimeApi: {
    quotes: vi.fn().mockResolvedValue({ items: {} }),
  },
  alertsApi: {
    history: vi.fn().mockResolvedValue({ items: [], unread_count: 0 }),
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

describe('OverviewPage', () => {
  it('renders page title', () => {
    renderWithProviders(<OverviewPage />)
    expect(screen.getByText(/cQuant 量化研究平台/)).toBeInTheDocument()
  })
})
