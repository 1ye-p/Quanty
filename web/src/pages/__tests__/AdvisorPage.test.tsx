import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AdvisorPage } from '../AdvisorPage'

vi.mock('@/hooks/useAdvisorStream', () => ({
  useAdvisorStream: () => ({
    state: {
      status: 'idle',
      sessionId: undefined,
      agents: {},
      report: '',
      ragPreview: '',
      activeAgent: null,
      error: null,
    },
    start: vi.fn(),
    reset: vi.fn(),
  }),
}))

vi.mock('@/lib/api', () => ({
  advisorApi: {
    chat: vi.fn().mockResolvedValue({ session_id: 's1', response: 'hello' }),
    report: vi.fn().mockResolvedValue({ report: '# Report' }),
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

describe('AdvisorPage', () => {
  it('renders page title', () => {
    renderWithProviders(<AdvisorPage />)
    expect(screen.getByText('AI 分析助手')).toBeInTheDocument()
  })
})
