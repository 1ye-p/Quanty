import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { PipelinePage } from '../PipelinePage'

vi.mock('@/lib/api', () => ({
  pipelineApi: {
    status: vi.fn().mockResolvedValue({ status: 'idle', stages: {} }),
    run: vi.fn().mockResolvedValue({ status: 'started' }),
  },
}))

describe('PipelinePage', () => {
  it('renders page title', () => {
    renderWithProviders(<PipelinePage />)
    expect(screen.getByText(/自动化回测管道/)).toBeInTheDocument()
  })
})
