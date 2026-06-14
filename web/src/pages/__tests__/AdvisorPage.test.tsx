import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { AdvisorPage } from '../AdvisorPage'

vi.mock('@/lib/api', () => ({
  advisorApi: {
    chat: vi.fn().mockResolvedValue({ response: 'test', sources: [] }),
    history: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}))

describe('AdvisorPage', () => {
  it('renders page title', () => {
    renderWithProviders(<AdvisorPage />)
    expect(screen.getByText(/AI 分析助手/)).toBeInTheDocument()
  })
})
