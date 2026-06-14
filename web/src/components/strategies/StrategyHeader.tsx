/**
 * Strategy detail page header with back button and action buttons.
 */

interface StrategyHeaderProps {
  title: string
  subtitle?: string
  onBack?: () => void
  actions?: React.ReactNode
}

export function StrategyHeader({ title, subtitle, onBack, actions }: StrategyHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          {onBack && (
            <button
              onClick={onBack}
              className="text-gray-400 hover:text-gray-600 text-sm"
            >
              &larr; Back
            </button>
          )}
          <h1 className="page-title">{title}</h1>
        </div>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}
