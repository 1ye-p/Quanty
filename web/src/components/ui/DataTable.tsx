import { useState, useMemo, type ReactNode } from 'react'

export interface Column<T> {
  key: string
  label: string
  sortable?: boolean
  searchable?: boolean
  filterable?: boolean
  filters?: string[]
  render?: (value: unknown, row: T) => ReactNode
  width?: string
}

interface BackendPagination {
  total: number
  page: number
  onPageChange: (page: number) => void
}

export interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  pageSize?: number
  loading?: boolean
  emptyText?: string
  onRowClick?: (row: T) => void
  rowKey: string | ((row: T) => string)
  searchPlaceholder?: string
  backendPagination?: BackendPagination
  rowClassName?: (row: T) => string
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  pageSize = 20,
  loading = false,
  emptyText = '暂无数据',
  onRowClick,
  rowKey,
  searchPlaceholder = '搜索...',
  backendPagination,
  rowClassName,
}: DataTableProps<T>) {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [activeFilters, setActiveFilters] = useState<Record<string, string[]>>({})
  const [page, setPage] = useState(0)

  const searchableKeys = useMemo(
    () => columns.filter(c => c.searchable).map(c => c.key),
    [columns],
  )

  const filtered = useMemo(() => {
    let result = data

    if (search && searchableKeys.length > 0) {
      const q = search.toLowerCase()
      result = result.filter(row =>
        searchableKeys.some(k => String(row[k] ?? '').toLowerCase().includes(q)),
      )
    }

    for (const [key, values] of Object.entries(activeFilters)) {
      if (values.length > 0) {
        result = result.filter(row => values.includes(String(row[key])))
      }
    }

    if (sortKey) {
      result = [...result].sort((a, b) => {
        const av = a[sortKey]
        const bv = b[sortKey]
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        const cmp = av < bv ? -1 : av > bv ? 1 : 0
        return sortDir === 'asc' ? cmp : -cmp
      })
    }

    return result
  }, [data, search, searchableKeys, sortKey, sortDir, activeFilters])

  const isBackend = !!backendPagination
  const totalPages = isBackend
    ? Math.ceil(backendPagination.total / pageSize)
    : Math.ceil(filtered.length / pageSize)
  const paged = isBackend
    ? data
    : filtered.slice(page * pageSize, (page + 1) * pageSize)

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function toggleFilter(key: string, value: string) {
    setActiveFilters(prev => {
      const current = prev[key] ?? []
      const next = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value]
      return { ...prev, [key]: next }
    })
    setPage(0)
  }

  if (loading) {
    return (
      <div className="card p-0 overflow-hidden">
        <div className="animate-pulse space-y-2 p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {!isBackend && (searchableKeys.length > 0 || columns.some(c => c.filterable)) && (
        <div className="flex flex-wrap gap-2 items-center">
          {searchableKeys.length > 0 && (
            <input
              className="input max-w-xs"
              placeholder={searchPlaceholder}
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
            />
          )}
          {columns.filter(c => c.filterable && c.filters).map(col => (
            <div key={col.key} className="flex gap-1 flex-wrap">
              {col.filters!.map(f => (
                <button
                  key={f}
                  className={`text-xs px-2 py-1 rounded-full border transition-colors ${
                    (activeFilters[col.key] ?? []).includes(f)
                      ? 'bg-brand-500 text-white border-brand-500'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
                  }`}
                  onClick={() => toggleFilter(col.key, f)}
                >
                  {f}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`table-th ${col.sortable ? 'cursor-pointer select-none hover:text-brand-600' : ''}`}
                  style={col.width ? { width: col.width } : undefined}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.sortable && sortKey === col.key && (
                      <span className="text-brand-500">{sortDir === 'asc' ? '↑' : '↓'}</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-td text-center text-gray-400 py-8">
                  {emptyText}
                </td>
              </tr>
            ) : (
              paged.map(row => (
                <tr
                  key={typeof rowKey === 'function' ? rowKey(row) : String(row[rowKey])}
                  className={`table-row ${onRowClick ? 'cursor-pointer' : ''} ${rowClassName?.(row) ?? ''}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map(col => (
                    <td key={col.key} className="table-td">
                      {col.render
                        ? col.render(row[col.key], row)
                        : String(row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            共 {isBackend ? backendPagination!.total : filtered.length} 条
          </span>
          <div className="flex gap-2 items-center">
            <button
              className="btn-secondary text-xs px-3 py-1"
              disabled={(isBackend ? backendPagination!.page : page) === 0}
              onClick={() => {
                if (isBackend) backendPagination!.onPageChange(backendPagination!.page - 1)
                else setPage(p => p - 1)
              }}
            >
              上一页
            </button>
            <span>
              {(isBackend ? backendPagination!.page : page) + 1} / {totalPages}
            </span>
            <button
              className="btn-secondary text-xs px-3 py-1"
              disabled={(isBackend ? backendPagination!.page : page) >= totalPages - 1}
              onClick={() => {
                if (isBackend) backendPagination!.onPageChange(backendPagination!.page + 1)
                else setPage(p => p + 1)
              }}
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
