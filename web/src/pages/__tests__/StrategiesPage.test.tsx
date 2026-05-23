import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { StrategiesPage } from '../StrategiesPage'

// Mock API module
vi.mock('@/lib/api', () => ({
  strategiesApi: {
    list: vi.fn().mockResolvedValue({
      items: [
        {
          strategy_id: 'momentum_v1',
          config: '{"strategy_type":"StaticTopN"}',
          parsed_config: { strategy_type: 'StaticTopN', top_n: 10, factors: ['ret_20d'] },
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    }),
    create: vi.fn().mockResolvedValue({ strategy_id: 'new_strat' }),
    update: vi.fn().mockResolvedValue({ strategy_id: 'momentum_v1' }),
    delete: vi.fn().mockResolvedValue({}),
  },
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  backtestsApi: {
    create: vi.fn().mockResolvedValue({ job_id: 'job-123', status: 'running' }),
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))

// Mock Monaco Editor
vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: { value: string; onChange?: (v: string) => void }) => (
    <textarea
      data-testid="monaco-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      readOnly={!onChange}
    />
  ),
}))

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
  Toaster: () => null,
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

describe('StrategiesPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title', () => {
    renderWithProviders(<StrategiesPage />)
    expect(screen.getByText('策略配置')).toBeInTheDocument()
  })

  it('renders strategy list after loading', async () => {
    renderWithProviders(<StrategiesPage />)
    await waitFor(() => {
      expect(screen.getByText('momentum_v1')).toBeInTheDocument()
    })
  })

  it('renders the page subtitle', () => {
    renderWithProviders(<StrategiesPage />)
    expect(screen.getByText(/JSON/)).toBeInTheDocument()
  })
})
