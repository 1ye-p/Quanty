import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { datasetsApi } from '@/lib/api'

interface AssetSearchProps {
  value: string
  onChange: (assetId: string) => void
}

export function AssetSearch({ value, onChange }: AssetSearchProps) {
  const [search, setSearch] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)

  useQuery({
    queryKey: ['assets-list'],
    queryFn: () => datasetsApi.list(200),
    staleTime: 300_000,
  })

  const filteredAssets = useMemo(() => {
    if (!search.trim()) return []
    // For now, just allow free-text input
    // In a real implementation, we'd query silver_assets
    return []
  }, [search])

  return (
    <div className="relative">
      <input
        type="text"
        value={search || value}
        onChange={e => {
          setSearch(e.target.value)
          onChange(e.target.value)
          setShowDropdown(true)
        }}
        onFocus={() => setShowDropdown(true)}
        onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
        placeholder="输入股票代码，如 SSE:600036"
        className="input-field w-full"
      />
      {showDropdown && filteredAssets.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {filteredAssets.map((asset: { asset_id: string }) => (
            <div
              key={asset.asset_id}
              className="px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
              onMouseDown={() => {
                onChange(asset.asset_id)
                setSearch(asset.asset_id)
                setShowDropdown(false)
              }}
            >
              {asset.asset_id}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
