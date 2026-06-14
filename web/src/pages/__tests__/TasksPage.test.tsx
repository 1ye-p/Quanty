import { renderWithProviders } from '../../test-utils'
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { TasksPage } from '../TasksPage'

vi.mock('@/lib/api', () => ({
  mlApi: {
    listExperiments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  backtestsApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  scoringApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
  jobsApi: {
    cancel: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

describe('TasksPage', () => {
  it('renders page title', () => {
    renderWithProviders(<TasksPage />)
    expect(screen.getByText(/任务管理/)).toBeInTheDocument()
  })
})
