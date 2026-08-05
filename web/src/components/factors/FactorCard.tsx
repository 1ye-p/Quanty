/**
 * Individual factor display card.
 * Shows factor name, category tags, description, and IC alert indicator.
 */
import { useTranslation } from 'react-i18next'
import { type FactorDefinition } from '@/lib/types'

interface FactorCardProps {
  factor: FactorDefinition
  selected: boolean
  hasAlert?: boolean
  alertMessage?: string
  onClick: () => void
  onAlertClick?: () => void
}

export function FactorCard({ factor, selected, hasAlert, alertMessage, onClick, onAlertClick }: FactorCardProps) {
  const { t } = useTranslation()
  return (
    <div
      onClick={onClick}
      className={`card cursor-pointer hover:shadow-md transition-shadow border-2 ${
        selected ? 'border-blue-500' : 'border-transparent'
      }`}
    >
      <div className="font-semibold text-gray-900 mb-1">
        {factor.name}
        {hasAlert && (
          <button
            className="ml-1 text-red-500 text-xs"
            title={alertMessage || t('component.factors.factor_card.ic_alert_default')}
            aria-label={t('component.factors.factor_card.alert_aria', { name: factor.name })}
            onClick={(e) => {
              e.stopPropagation()
              onAlertClick?.()
            }}
          >
            ⚠
          </button>
        )}
      </div>
      <div className="text-xs text-gray-500 mb-2">{factor.description || t('component.factors.factor_card.no_desc')}</div>
      <div className="flex flex-wrap gap-1">
        {factor.tags.map(tag => (
          <span key={tag} className="badge bg-blue-50 text-blue-700">{tag}</span>
        ))}
      </div>
      {factor.source === 'custom' && (
        <span className="mt-1 text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded inline-block">{t('component.factors.factor_card.custom_tag')}</span>
      )}
    </div>
  )
}
