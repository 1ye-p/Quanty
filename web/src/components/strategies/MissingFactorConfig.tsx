/**
 * MissingFactorConfig — Dropdown for missing factor handling.
 *
 * Options: fill 0 / fill median / exclude / risk penalty
 * Default: fill 0
 */
import { useTranslation } from 'react-i18next'

interface MissingFactorConfigProps {
  value: string
  onChange: (value: string) => void
}

const OPTIONS = [
  { value: 'fill_0', labelKey: 'component.strategies.missing_factor.fill_0' },
  { value: 'fill_median', labelKey: 'component.strategies.missing_factor.fill_median' },
  { value: 'exclude', labelKey: 'component.strategies.missing_factor.exclude' },
  { value: 'risk_penalty', labelKey: 'component.strategies.missing_factor.risk_penalty' },
] as const

export function MissingFactorConfig({ value, onChange }: MissingFactorConfigProps) {
  const { t } = useTranslation()
  return (
    <div>
      <label className="text-xs text-gray-500 mb-1 block">
        {t('component.strategies.missing_factor.label')}
      </label>
      <select
        className="input w-full"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        {OPTIONS.map(opt => (
          <option key={opt.value} value={opt.value}>
            {t(opt.labelKey)}
          </option>
        ))}
      </select>
    </div>
  )
}
