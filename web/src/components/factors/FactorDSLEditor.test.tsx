import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FactorDSLEditor } from './FactorDSLEditor'

vi.mock('@monaco-editor/react', () => {
  const Editor = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea data-testid="monaco-mock" value={value} onChange={e => onChange(e.target.value)} />
  )
  return { default: Editor }
})

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('FactorDSLEditor', () => {
  it('renders editor and preview button', async () => {
    render(<FactorDSLEditor onSave={vi.fn()} />, { wrapper })
    await waitFor(() => expect(screen.getByTestId('monaco-mock')).toBeInTheDocument())
    expect(screen.getByText('预览')).toBeInTheDocument()
    expect(screen.getByText('保存')).toBeInTheDocument()
  })

  it('shows examples panel toggle', () => {
    render(<FactorDSLEditor onSave={vi.fn()} />, { wrapper })
    expect(screen.getByText('语法说明 ▸')).toBeInTheDocument()
  })

  it('calls onSave with expression', async () => {
    const onSave = vi.fn()
    render(<FactorDSLEditor onSave={onSave} />, { wrapper })
    await waitFor(() => expect(screen.getByTestId('monaco-mock')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('monaco-mock'), { target: { value: 'rank(close)' } })
    fireEvent.click(screen.getByText('保存'))
    expect(onSave).toHaveBeenCalledWith('rank(close)', undefined)
  })
})
