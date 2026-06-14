import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { LivePage } from '../LivePage'

vi.mock('@/lib/api', () => ({
  liveApi: {
    listDeployments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listStrategies: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    strategies: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    deployed: vi.fn().mockResolvedValue({ items: [] }),
    getExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  tradingApi: {
    account: vi.fn().mockResolvedValue({ cash: 0, nav: 0 }),
    orders: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    positions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    fills: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    pnl: vi.fn().mockResolvedValue({ total_pnl: 0 }),
    placeOrder: vi.fn().mockResolvedValue({}),
    cancelOrder: vi.fn().mockResolvedValue({}),
  },
  jobsApi: {
    cancel: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
  realtimeApi: {
    quote: vi.fn().mockResolvedValue({}),
    quotes: vi.fn().mockResolvedValue({ items: {} }),
    market: vi.fn().mockResolvedValue({ items: {} }),
  },
}))

describe('LivePage', () => {
  it('renders page title', () => {
    renderWithProviders(<LivePage />)
    expect(screen.getByText(/实盘监控/)).toBeInTheDocument()
  })
})
