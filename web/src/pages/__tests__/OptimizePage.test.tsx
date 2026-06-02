import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { OptimizePage } from '../OptimizePage'

const _ResizeObserver = globalThis.ResizeObserver
beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})
afterAll(() => { globalThis.ResizeObserver = _ResizeObserver })

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
  mlApi: {
    predictions: vi.fn().mockResolvedValue({
      date: '2026-01-15',
      predictions: { 'A.SSE': 0.08, 'B.SZSE': 0.05 },
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

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(screen.getByText('优化结果')).toBeInTheDocument()
      expect(screen.getByText(/12\.00%/)).toBeInTheDocument()
      expect(screen.getByText(/0\.667/)).toBeInTheDocument()
    })
  })

  it('toggles advanced constraints section', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    expect(screen.queryByText('最大换手率 (%)')).not.toBeInTheDocument()

    await user.click(screen.getByText(/高级约束配置/))
    expect(screen.getByText('最大换手率 (%)')).toBeInTheDocument()
    expect(screen.getByText('换手率惩罚系数')).toBeInTheDocument()
  })

  it('shows per-asset weight bounds after covariance computed', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/高级约束配置/))

    expect(screen.getByText('单资产权重限制 (%)')).toBeInTheDocument()
    expect(screen.getByText('最小权重')).toBeInTheDocument()
    expect(screen.getByText('最大权重')).toBeInTheDocument()
  })

  it('passes constraints to optimize API', async () => {
    const { optimizeApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    // Compute covariance first
    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    // Open advanced constraints and set max turnover
    await user.click(screen.getByText(/高级约束配置/))
    const maxTurnoverInput = screen.getByPlaceholderText('不限')
    await user.type(maxTurnoverInput, '50')

    // Run optimization
    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(optimizeApi.optimize).toHaveBeenCalled()
    })

    // Verify the call included constraints with max_turnover
    const callArgs = vi.mocked(optimizeApi.optimize).mock.calls[0][0]
    expect(callArgs.constraints).toBeDefined()
    expect(callArgs.constraints!.max_turnover).toBe(0.5)
  })

  it('shows cost_aware fields when cost_aware optimizer is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const optimizerSelect = screen.getByDisplayValue(/mean_variance/)
    await user.selectOptions(optimizerSelect, 'cost_aware')

    expect(screen.getByText('交易成本率')).toBeInTheDocument()
    expect(screen.getByText('换手惩罚')).toBeInTheDocument()
  })

  it('shows expected returns table after covariance', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    expect(screen.getByText(/请先完成上方的协方差矩阵计算/)).toBeInTheDocument()

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText('预期年化收益率（%）')).toBeInTheDocument()
    })
  })

  it('shows turnover in results when metadata.turnover > 0', async () => {
    const { optimizeApi } = await import('@/lib/api')
    vi.mocked(optimizeApi.optimize).mockResolvedValueOnce({
      weights: { 'A.SSE': 0.6, 'B.SZSE': 0.4 },
      expected_return: 0.12,
      expected_volatility: 0.18,
      sharpe_ratio: 0.667,
      metadata: { turnover: 0.15 },
    })

    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(screen.getByText(/换手率：/)).toBeInTheDocument()
      expect(screen.getByText(/15\.0%/)).toBeInTheDocument()
    })
  })

  it('shows pie chart with weights distribution', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(screen.getByText('权重分布')).toBeInTheDocument()
      expect(screen.getByText('权重分配')).toBeInTheDocument()
    })
  })

  it('passes risk_parity optimizer to API', async () => {
    const { optimizeApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    const optimizerSelect = screen.getByDisplayValue(/mean_variance/)
    await user.selectOptions(optimizerSelect, 'risk_parity')

    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(optimizeApi.optimize).toHaveBeenCalled()
    })

    const callArgs = vi.mocked(optimizeApi.optimize).mock.calls[0][0]
    expect(callArgs.optimizer).toBe('risk_parity')
  })

  it('shows backtest navigation button in results', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />)

    const assetInput = screen.getAllByPlaceholderText(/600519/)[0]
    await user.type(assetInput, 'A.SSE, B.SZSE')
    await user.click(screen.getByText('计算协方差'))

    await waitFor(() => {
      expect(screen.getByText(/协方差矩阵已计算/)).toBeInTheDocument()
    })

    await user.click(screen.getByText('运行优化'))

    await waitFor(() => {
      expect(screen.getByText(/用这组权重运行回测/)).toBeInTheDocument()
    })
  })
})
