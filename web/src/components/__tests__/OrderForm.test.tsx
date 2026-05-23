import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OrderForm } from '../trading/OrderForm'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('OrderForm', () => {
  it('renders the form title', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByText('下单')).toBeInTheDocument()
  })

  it('renders symbol input', () => {
    renderWithProviders(<OrderForm />)
    expect(screen.getByPlaceholderText('600036')).toBeInTheDocument()
  })

  it('renders buy/sell buttons', () => {
    renderWithProviders(<OrderForm />)
    const buttons = screen.getAllByText(/买入|卖出/)
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })

  it('allows typing a symbol', () => {
    renderWithProviders(<OrderForm />)
    const input = screen.getByPlaceholderText('600036')
    fireEvent.change(input, { target: { value: '600036' } })
    expect(input).toHaveValue('600036')
  })

  it('allows switching side to sell', () => {
    renderWithProviders(<OrderForm />)
    // Initially: two buttons with "买入" (side toggle + submit)
    const buyButtons = screen.getAllByText('买入')
    expect(buyButtons.length).toBe(2)

    // Click the 卖出 side toggle
    const sellToggle = screen.getAllByText('卖出')[0]
    fireEvent.click(sellToggle)

    // After switching: submit button changes to 卖出, so now 1 买入 + 2 卖出
    const remainingBuy = screen.getAllByText('买入')
    const sellButtons = screen.getAllByText('卖出')
    expect(remainingBuy.length).toBe(1)
    expect(sellButtons.length).toBe(2)
  })

  it('renders quantity input with default value', () => {
    renderWithProviders(<OrderForm />)
    const qtyInput = screen.getByDisplayValue('1000')
    expect(qtyInput).toBeInTheDocument()
  })
})
