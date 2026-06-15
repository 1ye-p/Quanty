import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { TradingPage } from '../TradingPage'

vi.mock('@/lib/api', () => ({
  tradingApi: {
    account: vi.fn().mockResolvedValue({
      nav: 1000000,
      cash: 500000,
      positions_count: 3,
      realized_pnl: 10000,
      unrealized_pnl: 5000,
      gross_exposure: 600000,
      net_exposure: 500000,
    }),
    orders: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    positions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    pnl: vi.fn().mockResolvedValue({ total_pnl: 0, return_pct: 0 }),
  },
  realtimeApi: {
    quote: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('@/hooks/useRealtimeQuote', () => ({
  useRealtimeQuote: () => ({ quotes: {}, connected: false }),
}))

vi.mock('@/components/trading/AccountInfo', () => ({
  AccountInfo: ({ broker }: { broker: string }) => (
    <div data-testid="account-info">AccountInfo-{broker}</div>
  ),
}))

vi.mock('@/components/trading/OrderHistory', () => ({
  OrderHistory: ({ broker }: { broker: string }) => (
    <div data-testid="order-history">OrderHistory-{broker}</div>
  ),
}))

vi.mock('@/components/trading/TradeHistory', () => ({
  TradeHistory: ({ broker }: { broker: string }) => (
    <div data-testid="trade-history">TradeHistory-{broker}</div>
  ),
}))

describe('TradingPage', () => {
  it('renders page title', () => {
    renderWithProviders(<TradingPage />)
    expect(screen.getByText('交易中心')).toBeInTheDocument()
  })

  it('renders all four tabs', () => {
    renderWithProviders(<TradingPage />)
    // "下单" appears in both tab button and OrderForm heading, so use getAllByText
    const orderTab = screen.getAllByText('下单')
    expect(orderTab.length).toBeGreaterThanOrEqual(1)
    // Verify the tab-specific labels
    expect(screen.getByRole('button', { name: '下单' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '账户' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '订单历史' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '成交回报' })).toBeInTheDocument()
  })

  it('shows order tab content by default', () => {
    renderWithProviders(<TradingPage />)
    expect(screen.getByText('行情查询')).toBeInTheDocument()
    expect(screen.queryByTestId('account-info')).not.toBeInTheDocument()
    expect(screen.queryByTestId('order-history')).not.toBeInTheDocument()
    expect(screen.queryByTestId('trade-history')).not.toBeInTheDocument()
  })

  it('switches to account tab on click', async () => {
    renderWithProviders(<TradingPage />)
    fireEvent.click(screen.getByText('账户'))
    expect(screen.getByTestId('account-info')).toHaveTextContent('AccountInfo-paper')
    expect(screen.queryByText('行情查询')).not.toBeInTheDocument()
  })

  it('switches to orders tab on click', async () => {
    renderWithProviders(<TradingPage />)
    fireEvent.click(screen.getByText('订单历史'))
    expect(screen.getByTestId('order-history')).toHaveTextContent('OrderHistory-paper')
    expect(screen.queryByText('行情查询')).not.toBeInTheDocument()
  })

  it('switches to trades tab on click', async () => {
    renderWithProviders(<TradingPage />)
    fireEvent.click(screen.getByText('成交回报'))
    expect(screen.getByTestId('trade-history')).toHaveTextContent('TradeHistory-paper')
    expect(screen.queryByText('行情查询')).not.toBeInTheDocument()
  })

  it('passes broker to tab components', async () => {
    renderWithProviders(<TradingPage />)
    // Default broker is 'paper'
    fireEvent.click(screen.getByText('账户'))
    expect(screen.getByTestId('account-info')).toHaveTextContent('AccountInfo-paper')
  })
})
