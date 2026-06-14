import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { KnowledgePage } from '../KnowledgePage'

vi.mock('@/lib/api', () => ({
  knowledgeApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    search: vi.fn().mockResolvedValue({ hits: [], total_found: 0 }),
    ingest: vi.fn().mockResolvedValue({ doc_id: 'd1', status: 'ok' }),
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

describe('KnowledgePage', () => {
  it('renders page title', () => {
    renderWithProviders(<KnowledgePage />)
    expect(screen.getByText('知识库')).toBeInTheDocument()
  })
})
