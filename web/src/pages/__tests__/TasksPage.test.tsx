import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { TasksPage } from '../TasksPage'

vi.mock('@/lib/api', () => ({
  mlApi: {
    experiments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  backtestsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  scoringApi: {
    listSnapshots: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  jobsApi: {
    cancel: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
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

describe('TasksPage', () => {
  it('renders page title', () => {
    renderWithProviders(<TasksPage />)
    expect(screen.getByText('任务管理')).toBeInTheDocument()
  })
})
