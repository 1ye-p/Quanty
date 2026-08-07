import { render, screen, fireEvent } from '@testing-library/react'
import '../../test-utils'  // initializes global i18n singleton (zh-CN) for useTranslation()
import { describe, it, expect } from 'vitest'
import { DataTable, type Column } from './DataTable'

interface User { [key: string]: unknown; id: string; name: string; status: string; age: number }

const columns: Column<User>[] = [
  { key: 'name', label: 'Name', sortable: true, searchable: true },
  { key: 'status', label: 'Status', filterable: true, filters: ['active', 'inactive'] },
  { key: 'age', label: 'Age', sortable: true },
]

const data: User[] = [
  { id: '1', name: 'Alice', status: 'active', age: 30 },
  { id: '2', name: 'Bob', status: 'inactive', age: 25 },
  { id: '3', name: 'Charlie', status: 'active', age: 35 },
]

describe('DataTable', () => {
  it('renders rows', () => {
    render(<DataTable data={data} columns={columns} rowKey="id" />)
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
  })

  it('filters by search', () => {
    render(<DataTable data={data} columns={columns} rowKey="id" />)
    fireEvent.change(screen.getByPlaceholderText('搜索...'), { target: { value: 'Ali' } })
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.queryByText('Bob')).not.toBeInTheDocument()
  })

  it('sorts by column click', () => {
    render(<DataTable data={data} columns={columns} rowKey="id" />)
    fireEvent.click(screen.getByText('Age'))
    const rows = screen.getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Bob')
  })

  it('paginates', () => {
    const bigData = Array.from({ length: 25 }, (_, i) => ({
      id: String(i), name: `User${i}`, status: 'active', age: 20 + i,
    }))
    render(<DataTable data={bigData} columns={columns} rowKey="id" pageSize={10} />)
    expect(screen.getByText('User0')).toBeInTheDocument()
    expect(screen.queryByText('User10')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('下一页'))
    expect(screen.getByText('User10')).toBeInTheDocument()
  })

  it('shows empty text when no data', () => {
    render(<DataTable data={[]} columns={columns} rowKey="id" emptyText="No data" />)
    expect(screen.getByText('No data')).toBeInTheDocument()
  })

  it('applies rowClassName based on row data', () => {
    const rowClassName = (row: User) => row.status === 'inactive' ? 'bg-orange-50' : ''
    render(<DataTable data={data} columns={columns} rowKey="id" rowClassName={rowClassName} />)
    const rows = screen.getAllByRole('row')
    // rows[0] is header, rows[2] is Bob (inactive)
    expect(rows[2]).toHaveClass('bg-orange-50')
    expect(rows[1]).not.toHaveClass('bg-orange-50')
  })
})
