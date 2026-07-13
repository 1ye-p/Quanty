import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { marketApi } from '@/lib/api/market'

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

interface AssetSearchProps {
  value: string
  onChange: (assetId: string) => void
}

export function AssetSearch({ value, onChange }: AssetSearchProps) {
  const [search, setSearch] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const debouncedSearch = useDebouncedValue(search, 300)

  const { data: assetsData } = useQuery({
    queryKey: ['assets-search', debouncedSearch],
    queryFn: () => marketApi.searchAssets(debouncedSearch),
    enabled: debouncedSearch.length >= 2,
    staleTime: 60_000,
  })

  const filteredAssets = assetsData?.assets ?? []

  return (
    <div className="relative">
      <input
        type="text"
        value={search || value}
        onChange={e => {
          setSearch(e.target.value)
          setShowDropdown(true)
        }}
        onFocus={() => setShowDropdown(true)}
        onBlur={() => {
          setTimeout(() => {
            setShowDropdown(false)
            // If user typed but didn't select, clear search to show committed value
            if (search && search !== value) setSearch('')
          }, 200)
        }}
        placeholder="输入股票代码或名称，如 SSE:600036 或 招商"
        className="input-field w-full"
      />
      {showDropdown && filteredAssets.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {filteredAssets.map(asset => (
            <div
              key={asset.asset_id}
              className="px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
              onMouseDown={() => {
                onChange(asset.asset_id)
                setSearch(asset.asset_id)
                setShowDropdown(false)
              }}
            >
              <span className="font-mono">{asset.asset_id}</span>
              <span className="text-gray-500 ml-2">{asset.name}</span>
            </div>
          ))}
        </div>
      )}
      {showDropdown && search.length >= 2 && filteredAssets.length === 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg p-3 text-sm text-gray-400">
          无匹配结果
        </div>
      )}
    </div>
  )
}
