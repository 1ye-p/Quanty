/**
 * MissingFactorConfig — Dropdown for missing factor handling.
 *
 * Options: fill 0 / fill median / exclude
 * Default: fill 0
 */
interface MissingFactorConfigProps {
  value: string
  onChange: (value: string) => void
}

const OPTIONS = [
  { value: 'fill_0', label: '填 0', description: '缺失值填充为 0' },
  { value: 'fill_median', label: '填中位数', description: '缺失值填充为截面中位数' },
  { value: 'exclude', label: '排除', description: '缺失因子的股票不参与排名' },
]

export function MissingFactorConfig({ value, onChange }: MissingFactorConfigProps) {
  return (
    <div>
      <label className="text-xs text-gray-500 mb-1 block">缺失因子处理</label>
      <select
        className="input w-full"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        {OPTIONS.map(opt => (
          <option key={opt.value} value={opt.value}>
            {opt.label} — {opt.description}
          </option>
        ))}
      </select>
    </div>
  )
}
