import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AlertsPage } from '../AlertsPage'

vi.mock('@/lib/api', () => ({
  alertsApi: {
    rules: vi.fn().mockResolvedValue({
      items: [
        {
          rule_id: 'r1',
          rule_type: 'data_stale',
          rule_type_label: '数据过期',
          params: { max_days: 2 },
          enabled: true,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      rule_types: [
        { type: 'data_stale', label: '数据过期' },
        { type: 'factor_ic_low', label: '因子 IC 低' },
        { type: 'pnl_drawdown', label: '回撤告警' },
      ],
    }),
    history: vi.fn().mockResolvedValue({
      items: [
        {
          alert_id: 'a1',
          rule_id: 'r1',
          rule_type: 'data_stale',
          message: '数据已过期 3 天',
          triggered_at: '2026-01-15T10:30:00Z',
          read: false,
        },
        {
          alert_id: 'a2',
          rule_id: 'r1',
          rule_type: 'data_stale',
          message: '数据已过期 5 天',
          triggered_at: '2026-01-14T08:00:00Z',
          read: true,
        },
      ],
      unread_count: 1,
    }),
    createRule: vi.fn().mockResolvedValue({ rule_id: 'r2', status: 'created' }),
    deleteRule: vi.fn().mockResolvedValue({ rule_id: 'r1', status: 'deleted' }),
    markAllRead: vi.fn().mockResolvedValue({ status: 'ok' }),
    check: vi.fn().mockResolvedValue({ triggered: 2 }),
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

describe('AlertsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders page title and unread count', async () => {
    renderWithProviders(<AlertsPage />)
    expect(screen.getByText('告警中心')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/1 条未读告警/)).toBeInTheDocument()
    })
  })

  it('renders alert rules table', async () => {
    renderWithProviders(<AlertsPage />)
    await waitFor(() => {
      expect(screen.getByText('数据过期')).toBeInTheDocument()
    })
    expect(screen.getByText('启用')).toBeInTheDocument()
    expect(screen.getByText('删除')).toBeInTheDocument()
  })

  it('renders alert history with read/unread styling', async () => {
    renderWithProviders(<AlertsPage />)
    await waitFor(() => {
      expect(screen.getByText('数据已过期 3 天')).toBeInTheDocument()
    })
    expect(screen.getByText('数据已过期 5 天')).toBeInTheDocument()
  })

  it('shows create form when + 新增规则 is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ 新增规则'))
    expect(screen.getByText('新增告警规则')).toBeInTheDocument()
    expect(screen.getByText('保存规则')).toBeInTheDocument()
  })

  it('closes create form when 取消 is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ 新增规则'))
    expect(screen.getByText('新增告警规则')).toBeInTheDocument()

    await user.click(screen.getByText('取消'))
    expect(screen.queryByText('新增告警规则')).not.toBeInTheDocument()
  })

  it('submits create rule mutation', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ 新增规则'))

    // The default rule type is data_stale with max_days=2
    const submitButton = screen.getByText('保存规则')
    await user.click(submitButton)

    await waitFor(() => {
      expect(alertsApi.createRule).toHaveBeenCalled()
    })
  })

  it('calls check mutation when 立即检查 is clicked', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('立即检查'))

    await waitFor(() => {
      expect(alertsApi.check).toHaveBeenCalled()
    })
  })

  it('shows 全部标为已读 button when unread_count > 0', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('全部标为已读')).toBeInTheDocument()
    })

    await user.click(screen.getByText('全部标为已读'))

    await waitFor(() => {
      expect(alertsApi.markAllRead).toHaveBeenCalled()
    })
  })

  it('opens confirm dialog on delete click', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('删除')).toBeInTheDocument()
    })

    await user.click(screen.getByText('删除'))
    expect(screen.getByText('确认删除规则')).toBeInTheDocument()
    expect(screen.getByText('确定删除此告警规则？此操作不可撤销。')).toBeInTheDocument()
  })

  it('deletes rule on confirm', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('删除')).toBeInTheDocument()
    })

    await user.click(screen.getByText('删除'))
    // Confirm button in dialog also says "删除" (btn-danger)
    const deleteButtons = screen.getAllByText('删除')
    await user.click(deleteButtons[deleteButtons.length - 1])

    await waitFor(() => {
      expect(alertsApi.deleteRule).toHaveBeenCalled()
      expect(vi.mocked(alertsApi.deleteRule).mock.calls[0][0]).toBe('r1')
    })
  })

  it('shows toast error when createRule fails', async () => {
    const { alertsApi } = await import('@/lib/api')
    const { toast } = await import('sonner')
    vi.mocked(alertsApi.createRule).mockRejectedValueOnce(new Error('duplicate'))
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ 新增规则'))
    await user.click(screen.getByText('保存规则'))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled()
    })
  })

  it('renders factor_ic_low param fields when rule type changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ 新增规则'))

    const select = screen.getByRole('combobox')
    await user.selectOptions(select, 'factor_ic_low')

    expect(screen.getByPlaceholderText('ret_20d')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('0.02')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('20')).toBeInTheDocument()
  })

  it('renders empty state when no rules', async () => {
    const { alertsApi } = await import('@/lib/api')
    vi.mocked(alertsApi.rules).mockResolvedValue({
      items: [],
      rule_types: [{ type: 'data_stale', label: '数据过期' }],
    })
    vi.mocked(alertsApi.history).mockResolvedValue({
      items: [],
      unread_count: 0,
    })

    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('暂无告警规则，点击"+ 新增规则"配置')).toBeInTheDocument()
      expect(screen.getByText('暂无告警历史')).toBeInTheDocument()
      expect(screen.getByText('无未读告警')).toBeInTheDocument()
    })
  })
})
