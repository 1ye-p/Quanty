import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { NewsPage } from '../NewsPage'

vi.mock('@/lib/api', () => ({
  newsApi: {
    listEvents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    stats: vi.fn().mockResolvedValue({ total: 0, today: 0, avg_sentiment: 0 }),
    assetSentiment: vi.fn().mockResolvedValue({ dates: [], values: [], counts: [] }),
  },
}))

describe('NewsPage', () => {
  it('renders page title', () => {
    renderWithProviders(<NewsPage />)
    expect(screen.getByText(/消息面/)).toBeInTheDocument()
  })
})
