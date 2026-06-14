/**
 * Advanced constraints configuration for portfolio optimization.
 * Includes per-asset bounds, sector limits, factor exposure limits, and tracking error.
 */
import type { } from 'react'

interface SectorEntry {
  label: string
  assets: string
  min: string
  max: string
}

interface FactorEntry {
  name: string
  min: string
  max: string
  loadings: Record<string, string>
}

interface ConstraintsTabProps {
  covResult: Record<string, Record<string, number>> | null
  maxTurnover: string
  onMaxTurnoverChange: (val: string) => void
  turnoverPenalty: string
  onTurnoverPenaltyChange: (val: string) => void
  maxTrackingError: string
  onMaxTrackingErrorChange: (val: string) => void
  excludeST: boolean
  onExcludeSTChange: (val: boolean) => void
  excludeSuspended: boolean
  onExcludeSuspendedChange: (val: boolean) => void
  excludeAssetsText: string
  onExcludeAssetsTextChange: (val: string) => void
  perAssetBounds: Record<string, { min: string; max: string }>
  onPerAssetBoundsChange: (bounds: Record<string, { min: string; max: string }>) => void
  sectorEntries: SectorEntry[]
  onSectorEntriesChange: (entries: SectorEntry[]) => void
  factorEntries: FactorEntry[]
  onFactorEntriesChange: (entries: FactorEntry[]) => void
}

export function ConstraintsTab({
  covResult,
  maxTurnover, onMaxTurnoverChange,
  turnoverPenalty, onTurnoverPenaltyChange,
  maxTrackingError, onMaxTrackingErrorChange,
  excludeST, onExcludeSTChange,
  excludeSuspended, onExcludeSuspendedChange,
  excludeAssetsText, onExcludeAssetsTextChange,
  perAssetBounds, onPerAssetBoundsChange,
  sectorEntries, onSectorEntriesChange,
  factorEntries, onFactorEntriesChange,
}: ConstraintsTabProps) {
  const assets = covResult ? Object.keys(covResult) : []

  const addSector = () => onSectorEntriesChange([...sectorEntries, { label: '', assets: '', min: '0', max: '30' }])
  const removeSector = (idx: number) => onSectorEntriesChange(sectorEntries.filter((_, i) => i !== idx))
  const updateSector = (idx: number, field: keyof SectorEntry, value: string) => {
    onSectorEntriesChange(sectorEntries.map((e, i) => i === idx ? { ...e, [field]: value } : e))
  }

  const addFactor = () => onFactorEntriesChange([...factorEntries, { name: '', min: '-0.5', max: '0.5', loadings: {} }])
  const removeFactor = (idx: number) => onFactorEntriesChange(factorEntries.filter((_, i) => i !== idx))
  const updateFactor = (idx: number, field: keyof FactorEntry, value: string) => {
    onFactorEntriesChange(factorEntries.map((e, i) => i === idx ? { ...e, [field]: value } : e))
  }
  const updateFactorLoading = (factorIdx: number, asset: string, value: string) => {
    onFactorEntriesChange(factorEntries.map((e, i) => {
      if (i !== factorIdx) return e
      return { ...e, loadings: { ...e.loadings, [asset]: value } }
    }))
  }

  return (
    <div className="mt-2 space-y-4 p-3 bg-gray-50 rounded-lg">
      {/* Turnover */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">Max Turnover (%)</label>
          <input type="number" value={maxTurnover} onChange={e => onMaxTurnoverChange(e.target.value)}
            className="input w-full" placeholder="Unlimited" min={0} max={200} step={5} />
          <p className="text-xs text-gray-400 mt-0.5">Leave empty for no limit</p>
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">Turnover Penalty</label>
          <input type="number" value={turnoverPenalty} onChange={e => onTurnoverPenaltyChange(e.target.value)}
            className="input w-full" min={0} max={0.01} step={0.0001} />
        </div>
      </div>

      {/* Per-Asset Bounds */}
      {assets.length > 0 && (
        <div>
          <label className="block text-xs text-gray-600 mb-1.5">Per-Asset Weight Bounds (%)</label>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500">
                <th className="text-left py-1 pr-2">Asset</th>
                <th className="text-left py-1 pr-2 w-24">Min Weight</th>
                <th className="text-left py-1 w-24">Max Weight</th>
              </tr>
            </thead>
            <tbody>
              {assets.map(asset => (
                <tr key={asset} className="border-t border-gray-200">
                  <td className="py-1 pr-2 font-mono text-gray-700">{asset}</td>
                  <td className="py-1 pr-2">
                    <input type="number"
                      value={perAssetBounds[asset]?.min ?? ''}
                      onChange={e => onPerAssetBoundsChange({
                        ...perAssetBounds,
                        [asset]: { min: e.target.value, max: perAssetBounds[asset]?.max ?? '' }
                      })}
                      className="input w-full text-xs" placeholder="0" min={0} max={100} step={1} />
                  </td>
                  <td className="py-1">
                    <input type="number"
                      value={perAssetBounds[asset]?.max ?? ''}
                      onChange={e => onPerAssetBoundsChange({
                        ...perAssetBounds,
                        [asset]: { min: perAssetBounds[asset]?.min ?? '', max: e.target.value }
                      })}
                      className="input w-full text-xs" placeholder="100" min={0} max={100} step={1} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sector Limits */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-xs text-gray-600">Sector Exposure Limits</label>
          <button type="button" onClick={addSector}
            className="text-xs text-blue-600 hover:underline">+ Add Sector</button>
        </div>
        {sectorEntries.length === 0 && (
          <p className="text-xs text-gray-400">No sector limits. Click above to add.</p>
        )}
        {sectorEntries.map((entry, idx) => (
          <div key={idx} className="flex items-end gap-2 mb-2 p-2 bg-white rounded border border-gray-200">
            <div className="flex-1">
              <label className="text-[10px] text-gray-500 block">Sector Name</label>
              <input value={entry.label} onChange={e => updateSector(idx, 'label', e.target.value)}
                className="input w-full text-xs" placeholder="Banking" />
            </div>
            <div className="flex-[2]">
              <label className="text-[10px] text-gray-500 block">Assets (comma-separated)</label>
              <input value={entry.assets} onChange={e => updateSector(idx, 'assets', e.target.value)}
                className="input w-full text-xs" placeholder="601398.SSE, 601288.SSE" />
            </div>
            <div className="w-20">
              <label className="text-[10px] text-gray-500 block">Min (%)</label>
              <input type="number" value={entry.min} onChange={e => updateSector(idx, 'min', e.target.value)}
                className="input w-full text-xs" min={0} max={100} step={1} />
            </div>
            <div className="w-20">
              <label className="text-[10px] text-gray-500 block">Max (%)</label>
              <input type="number" value={entry.max} onChange={e => updateSector(idx, 'max', e.target.value)}
                className="input w-full text-xs" min={0} max={100} step={1} />
            </div>
            <button type="button" onClick={() => removeSector(idx)}
              className="text-red-400 hover:text-red-600 text-sm px-1 pb-0.5">x</button>
          </div>
        ))}
      </div>

      {/* Factor Exposure Limits */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-xs text-gray-600">Factor Exposure Limits</label>
          <button type="button" onClick={addFactor}
            className="text-xs text-blue-600 hover:underline">+ Add Factor</button>
        </div>
        {factorEntries.length === 0 && (
          <p className="text-xs text-gray-400">No factor limits. Click above to add.</p>
        )}
        {factorEntries.map((entry, idx) => (
          <div key={idx} className="mb-2 p-2 bg-white rounded border border-gray-200">
            <div className="flex items-end gap-2 mb-2">
              <div className="flex-1">
                <label className="text-[10px] text-gray-500 block">Factor Name</label>
                <input value={entry.name} onChange={e => updateFactor(idx, 'name', e.target.value)}
                  className="input w-full text-xs" placeholder="momentum" />
              </div>
              <div className="w-24">
                <label className="text-[10px] text-gray-500 block">Min Exposure</label>
                <input type="number" value={entry.min} onChange={e => updateFactor(idx, 'min', e.target.value)}
                  className="input w-full text-xs" step={0.1} />
              </div>
              <div className="w-24">
                <label className="text-[10px] text-gray-500 block">Max Exposure</label>
                <input type="number" value={entry.max} onChange={e => updateFactor(idx, 'max', e.target.value)}
                  className="input w-full text-xs" step={0.1} />
              </div>
              <button type="button" onClick={() => removeFactor(idx)}
                className="text-red-400 hover:text-red-600 text-sm px-1 pb-0.5">x</button>
            </div>
            {assets.length > 0 && (
              <div>
                <label className="text-[10px] text-gray-500 block mb-1">
                  Factor Loadings (per-asset exposure to this factor)
                </label>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                  {assets.map(asset => (
                    <div key={asset} className="flex items-center gap-1">
                      <span className="font-mono text-[10px] text-gray-600 truncate" style={{ maxWidth: 120 }}>
                        {asset}
                      </span>
                      <input type="number" step={0.01}
                        value={entry.loadings[asset] ?? ''}
                        onChange={e => updateFactorLoading(idx, asset, e.target.value)}
                        className="input w-full text-[10px] py-0" placeholder="0" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Max Tracking Error */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">Max Tracking Error (annualized)</label>
          <input type="number" value={maxTrackingError}
            onChange={e => onMaxTrackingErrorChange(e.target.value)}
            className="input w-full" placeholder="Unlimited" min={0} max={1} step={0.005} />
          <p className="text-xs text-gray-400 mt-0.5">Leave empty for no limit, e.g. 0.05 = 5%</p>
        </div>
      </div>

      {/* Asset Exclusion */}
      <div>
        <label className="block text-xs text-gray-600 mb-1.5">Asset Exclusion</label>
        <div className="flex items-center gap-4 mb-2">
          <label className="flex items-center gap-1.5 text-xs text-gray-700">
            <input type="checkbox" checked={excludeST}
              onChange={e => onExcludeSTChange(e.target.checked)} />
            Exclude ST / *ST stocks
          </label>
          <label className="flex items-center gap-1.5 text-xs text-gray-700">
            <input type="checkbox" checked={excludeSuspended}
              onChange={e => onExcludeSuspendedChange(e.target.checked)} />
            Exclude suspended stocks
          </label>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 block">Custom exclusion list (comma-separated asset IDs)</label>
          <input value={excludeAssetsText}
            onChange={e => onExcludeAssetsTextChange(e.target.value)}
            className="input w-full text-xs"
            placeholder="000001.SZSE, 600000.SSE" />
        </div>
      </div>
    </div>
  )
}
