import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { DatasetsPage } from '../DatasetsPage'

vi.mock('@/lib/api', () => ({
  datasetsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    quality: vi.fn().mockResolvedValue({ score: 0, issues: [] }),
    scheduleStatus: vi.fn().mockResolvedValue({ enabled: false }),
    freshness: vi.fn().mockResolvedValue({ last_updated: null }),
  },
}))

describe('DatasetsPage', () => {
  it('renders page title', () => {
    renderWithProviders(<DatasetsPage />)
    expect(screen.getByText('数据集')).toBeInTheDocument()
  })
})
