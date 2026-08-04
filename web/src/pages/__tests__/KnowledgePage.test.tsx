import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { KnowledgePage } from '../KnowledgePage'

vi.mock('@/lib/api', () => ({
  knowledgeApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    search: vi.fn().mockResolvedValue({ results: [] }),
  },
}))

describe('KnowledgePage', () => {
  it('renders page title', () => {
    renderWithProviders(<KnowledgePage />)
    expect(screen.getByText('知识库')).toBeInTheDocument()
  })
})
