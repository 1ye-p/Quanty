import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { ScoringPage } from '../ScoringPage'

vi.mock('@/lib/api', () => ({
  scoringApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    result: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))

describe('ScoringPage', () => {
  it('renders page title', () => {
    renderWithProviders(<ScoringPage />)
    expect(screen.getByText(/截面打分/)).toBeInTheDocument()
  })
})
