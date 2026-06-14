import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { NewsPage } from '../NewsPage'

vi.mock('@/lib/api', () => ({
  newsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    stats: vi.fn().mockResolvedValue({
      total_events: 0,
      avg_sentiment: null,
      source_counts: {},
      event_type_counts: {},
      daily_sentiment: [],
    }),
    get: vi.fn().mockResolvedValue(null),
    getAssetSentiment: vi.fn().mockResolvedValue({ dates: [], values: [], counts: [] }),
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

describe('NewsPage', () => {
  it('renders page title', () => {
    renderWithProviders(<NewsPage />)
    expect(screen.getByText('消息面')).toBeInTheDocument()
  })
})
