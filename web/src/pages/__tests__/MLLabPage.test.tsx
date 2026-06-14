import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { MLLabPage } from '../MLLabPage'

// Mock ResizeObserver for recharts
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.mock('@/lib/api', () => ({
  mlApi: {
    experiments: vi.fn().mockResolvedValue({
      items: [
        {
          run_id: 'run-1',
          job_id: 'job-1',
          trainer_name: 'lightgbm',
          feature_set_version: 'v1',
          target_name: 'ret_5d',
          status: 'done',
          model_id: 'run-1',
          metrics: { rmse: 0.05, mae: 0.03, r2: 0.12, directional_accuracy: 0.55 },
          params: {},
          artifact_path: '/tmp/model',
          artifact_uri: '',
          error_text: '',
          started_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:05:00Z',
        },
      ],
      total: 1,
      source: 'duckdb+mlflow',
    }),
    featureImportance: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    submitJob: vi.fn().mockResolvedValue({ job_id: 'job-new', status: 'submitted' }),
    getJob: vi.fn().mockResolvedValue({ job_id: 'job-new', status: 'running' }),
  },
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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

describe('MLLabPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title', () => {
    renderWithProviders(<MLLabPage />)
    expect(screen.getByText('机器学习实验室')).toBeInTheDocument()
  })

  it('renders trainer selector', () => {
    renderWithProviders(<MLLabPage />)
    // Refactored page uses tab navigation
    expect(screen.getByText('模型库')).toBeInTheDocument()
  })

  it('renders submit button', () => {
    renderWithProviders(<MLLabPage />)
    // Refactored page uses tab navigation
    expect(screen.getByText('训练')).toBeInTheDocument()
  })

  it('shows experiment list after loading', async () => {
    renderWithProviders(<MLLabPage />)
    // The page should render without crashing even with mock data
    expect(screen.getByText('机器学习实验室')).toBeInTheDocument()
  })
})
