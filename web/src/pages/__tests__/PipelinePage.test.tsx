import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { PipelinePage } from '../PipelinePage'

vi.mock('@/lib/api', () => ({
  pipelineApi: {
    status: vi.fn().mockResolvedValue({
      status: 'idle',
      stages: {},
      run_id: null,
      detail: null,
      started_at: null,
      finished_at: null,
      duration_seconds: null,
    }),
    run: vi.fn().mockResolvedValue({ run_id: 'p1', status: 'started' }),
  },
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

describe('PipelinePage', () => {
  it('renders page title', () => {
    renderWithProviders(<PipelinePage />)
    expect(screen.getByText('自动化回测管道')).toBeInTheDocument()
  })
})
