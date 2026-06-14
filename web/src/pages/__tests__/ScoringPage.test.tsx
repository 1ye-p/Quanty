import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ScoringPage } from '../ScoringPage'

vi.mock('@/lib/api', () => ({
  scoringApi: {
    run: vi.fn().mockResolvedValue({ run_id: 'r1', status: 'running' }),
    getResult: vi.fn().mockResolvedValue(null),
    listSnapshots: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  factorAnalyticsApi: {
    definitions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
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

describe('ScoringPage', () => {
  it('renders page title', () => {
    renderWithProviders(<ScoringPage />)
    expect(screen.getByText('截面打分')).toBeInTheDocument()
  })
})
