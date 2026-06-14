import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { DatasetsPage } from '../DatasetsPage'

vi.mock('@/lib/api', () => ({
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    quality: vi.fn().mockResolvedValue(null),
    scheduleStatus: vi.fn().mockResolvedValue(null),
    triggerIngest: vi.fn().mockResolvedValue({}),
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

describe('DatasetsPage', () => {
  it('renders page title', () => {
    renderWithProviders(<DatasetsPage />)
    expect(screen.getByText('数据集')).toBeInTheDocument()
  })
})
