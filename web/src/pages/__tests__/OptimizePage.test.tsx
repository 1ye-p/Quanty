import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { OptimizePage } from '../OptimizePage'

// Mock ResizeObserver for recharts
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.mock('@/lib/api', () => ({
  optimizeApi: {
    covariance: vi.fn().mockResolvedValue({
      covariance: {
        'A.SSE': { 'A.SSE': 0.04, 'B.SZSE': 0.01 },
        'B.SZSE': { 'A.SSE': 0.01, 'B.SZSE': 0.09 },
      },
      assets: ['A.SSE', 'B.SZSE'],
      method: 'historical',
      as_of_date: '2026-01-01',
    }),
    optimize: vi.fn().mockResolvedValue({
      weights: { 'A.SSE': 0.6, 'B.SZSE': 0.4 },
      expected_return: 0.12,
      expected_volatility: 0.18,
      sharpe_ratio: 0.667,
      metadata: {},
    }),
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

describe('OptimizePage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title', () => {
    renderWithProviders(<OptimizePage />)
    expect(screen.getByText('组合优化')).toBeInTheDocument()
  })

  it('renders covariance section', () => {
    renderWithProviders(<OptimizePage />)
    expect(screen.getByText('协方差计算')).toBeInTheDocument()
    // Multiple inputs have 600519 placeholder, check at least one exists
    expect(screen.getAllByPlaceholderText(/600519/).length).toBeGreaterThanOrEqual(1)
  })

  it('renders optimizer section', () => {
    renderWithProviders(<OptimizePage />)
    expect(screen.getByText('优化器配置')).toBeInTheDocument()
    expect(screen.getByDisplayValue('mean_variance — 均值方差')).toBeInTheDocument()
  })

  it('computes covariance and shows result', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })
  })

  it('runs optimization after covariance', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    // First compute covariance
    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    // Then optimize
    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(screen.getByText('优化结果')).toBeInTheDocument()
      expect(screen.getByText(/12\.00%/)).toBeInTheDocument()
      expect(screen.getByText(/0\.667/)).toBeInTheDocument()
    })
  })
})
