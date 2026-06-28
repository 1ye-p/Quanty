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
    expect(screen.getByText('alerts.center')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/1 alerts.unread_count/)).toBeInTheDocument()
    })
  })

  it('renders alert rules table', async () => {
    renderWithProviders(<AlertsPage />)
    await waitFor(() => {
      expect(screen.getByText('数据过期')).toBeInTheDocument()
    })
    expect(screen.getByText('common.enabled')).toBeInTheDocument()
    expect(screen.getByText('common.delete')).toBeInTheDocument()
  })

  it('renders alert history with read/unread styling', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)
    // Click on history tab
    await user.click(screen.getByText('alerts.tabs.history'))
    await waitFor(() => {
      expect(screen.getByText('数据已过期 3 天')).toBeInTheDocument()
    })
    expect(screen.getByText('数据已过期 5 天')).toBeInTheDocument()
  })

  it('shows create form when + alerts.new_rule is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ alerts.new_rule'))
    expect(screen.getByText('alerts.new_alert_rule')).toBeInTheDocument()
    expect(screen.getByText('common.save')).toBeInTheDocument()
  })

  it('closes create form when common.cancel is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ alerts.new_rule'))
    expect(screen.getByText('alerts.new_alert_rule')).toBeInTheDocument()

    await user.click(screen.getByText('common.cancel'))
    expect(screen.queryByText('alerts.new_alert_rule')).not.toBeInTheDocument()
  })

  it('submits create rule mutation', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ alerts.new_rule'))

    // The default rule type is data_stale with max_days=2
    const submitButton = screen.getByText('common.save')
    await user.click(submitButton)

    await waitFor(() => {
      expect(alertsApi.createRule).toHaveBeenCalled()
    })
  })

  it('calls check mutation when alerts.check_now is clicked', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('alerts.check_now'))

    await waitFor(() => {
      expect(alertsApi.check).toHaveBeenCalled()
    })
  })

  it('shows alerts.mark_all_read button when unread_count > 0', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('alerts.mark_all_read')).toBeInTheDocument()
    })

    await user.click(screen.getByText('alerts.mark_all_read'))

    await waitFor(() => {
      expect(alertsApi.markAllRead).toHaveBeenCalled()
    })
  })

  it('opens confirm dialog on delete click', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('common.delete')).toBeInTheDocument()
    })

    await user.click(screen.getByText('common.delete'))
    expect(screen.getByText('alerts.confirm_delete_rule')).toBeInTheDocument()
    expect(screen.getByText('alerts.confirm_delete_message')).toBeInTheDocument()
  })

  it('deletes rule on confirm', async () => {
    const { alertsApi } = await import('@/lib/api')
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('common.delete')).toBeInTheDocument()
    })

    await user.click(screen.getByText('common.delete'))
    // Confirm button in dialog also says "common.delete" (btn-danger)
    const deleteButtons = screen.getAllByText('common.delete')
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

    await user.click(screen.getByText('+ alerts.new_rule'))
    await user.click(screen.getByText('common.save'))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled()
    })
  })

  it('renders factor_ic_low param fields when rule type changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await user.click(screen.getByText('+ alerts.new_rule'))

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

    const user = userEvent.setup()
    renderWithProviders(<AlertsPage />)

    await waitFor(() => {
      expect(screen.getByText('alerts.no_rules_hint')).toBeInTheDocument()
    })

    // Click on history tab to see history empty state
    await user.click(screen.getByText('alerts.tabs.history'))
    await waitFor(() => {
      expect(screen.getByText('alerts.no_history')).toBeInTheDocument()
    })
  })
})
