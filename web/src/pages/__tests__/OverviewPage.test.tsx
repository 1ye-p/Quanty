import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { OverviewPage } from '../OverviewPage'

vi.mock('@/lib/api', () => ({
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  alertsApi: {
    history: vi.fn().mockResolvedValue({ items: [], unread_count: 0 }),
  },
  backtestsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  mlApi: {
    listExperiments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  liveApi: {
    listDeployments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  realtimeApi: {
    quotes: vi.fn().mockResolvedValue({}),
  },
}))

describe('OverviewPage', () => {
  it('renders page title', () => {
    renderWithProviders(<OverviewPage />)
    expect(screen.getByText(/cQuant 量化研究平台/)).toBeInTheDocument()
  })
})
