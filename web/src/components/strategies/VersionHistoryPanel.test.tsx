import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { VersionHistoryPanel } from './VersionHistoryPanel'

const mockVersions = [
  { version_id: 'v1', config_text: '{"top_n": 10}', config_format: 'json', summary: 'StaticTopN · top_n=10', created_at: '2026-06-01T10:00:00Z' },
  { version_id: 'v2', config_text: '{"top_n": 5}', config_format: 'json', summary: 'StaticTopN · top_n=5', created_at: '2026-06-01T09:00:00Z' },
]

describe('VersionHistoryPanel', () => {
  it('renders version list after expanding', () => {
    render(<VersionHistoryPanel versions={mockVersions} onRollback={vi.fn()} />)
    // Panel starts collapsed; click the header to expand
    fireEvent.click(screen.getByText(/版本历史/))
    expect(screen.getByText(/v1/)).toBeInTheDocument()
    expect(screen.getByText('StaticTopN · top_n=10')).toBeInTheDocument()
  })

  it('calls onRollback', () => {
    const onRollback = vi.fn()
    render(<VersionHistoryPanel versions={mockVersions} onRollback={onRollback} />)
    // Expand first
    fireEvent.click(screen.getByText(/版本历史/))
    fireEvent.click(screen.getAllByText('回滚')[0])
    expect(onRollback).toHaveBeenCalledWith('v1')
  })

  it('shows empty state', () => {
    render(<VersionHistoryPanel versions={[]} onRollback={vi.fn()} />)
    expect(screen.getByText('暂无版本历史')).toBeInTheDocument()
  })
})
