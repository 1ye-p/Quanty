import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { riskApi } from '@/lib/api/risk'
import { extendedQueryKeys } from '@/lib/queryKeys'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'

const STYLE_FACTORS = ['market_cap', 'value', 'momentum', 'volatility', 'turnover', 'quality']

interface FactorRiskPanelProps {
  weights: Record<string, number>
}

export const FactorRiskPanel: React.FC<FactorRiskPanelProps> = ({ weights }) => {
  const { t } = useTranslation()
  const weightsJson = useMemo(() => JSON.stringify(weights), [weights])

  const styleLabel = (factor: string): string =>
    t(`component.risk.factor_risk.style.${factor}`, { defaultValue: factor })

  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.risk.factorDecomposition(weightsJson),
    queryFn: () => riskApi.getFactorDecomposition({ weights_json: weightsJson }),
    enabled: Object.keys(weights).length > 0,
  })

  if (!Object.keys(weights).length) {
    return <div className="text-center py-8 text-gray-400">{t('component.risk.factor_risk.empty')}</div>
  }
  if (isLoading) return <div className="text-center py-4 text-gray-500">{t('common.loading')}</div>
  if (error) return <div className="text-center py-8 text-red-500">{t('component.risk.factor_risk.load_failed', { message: error.message })}</div>
  if (!data) return null

  const { style_exposures, risk_decomposition } = data
  const {
    total_risk, factor_risk, idiosyncratic_risk, factor_risk_pct,
    style_risk_contributions, industry_risk_contributions,
  } = risk_decomposition

  // Radar chart data
  const radarData = STYLE_FACTORS.map(f => ({
    factor: styleLabel(f),
    exposure: Math.round((style_exposures[f] ?? 0) * 10000) / 100,
  }))

  // Style risk contribution data (sorted desc)
  const styleRiskData = Object.entries(style_risk_contributions)
    .map(([k, v]) => ({ name: styleLabel(k), value: v }))
    .sort((a, b) => b.value - a.value)

  // Industry risk contribution data (top 10)
  const industryRiskData = Object.entries(industry_risk_contributions)
    .map(([k, v]) => ({ name: k, value: v }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">{t('component.risk.factor_risk.total_risk')}</div>
          <div className="text-2xl font-semibold">{(total_risk * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">{t('component.risk.factor_risk.factor_risk')}</div>
          <div className="text-2xl font-semibold text-indigo-600">{(factor_risk * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">{t('component.risk.factor_risk.factor_risk_pct')}</div>
          <div className="text-2xl font-semibold text-indigo-600">{Number(factor_risk_pct).toFixed(1)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">{t('component.risk.factor_risk.idiosyncratic_risk')}</div>
          <div className="text-2xl font-semibold text-gray-800">{(idiosyncratic_risk * 100).toFixed(2)}%</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Style Exposure Radar */}
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-medium text-gray-800 mb-4">{t('component.risk.factor_risk.style_exposure_title')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
              <PolarGrid />
              <PolarAngleAxis dataKey="factor" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis tick={{ fontSize: 10 }} />
              <Radar name={t('component.risk.factor_risk.exposure')} dataKey="exposure" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              <Tooltip formatter={(v: number) => [`${v}%`, t('component.risk.factor_risk.exposure')]} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Style Risk Contributions */}
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-medium text-gray-800 mb-4">{t('component.risk.factor_risk.style_risk_title')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={styleRiskData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={60} />
              <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, t('component.risk.factor_risk.risk_contribution')]} />
              <Bar dataKey="value" fill="#818cf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Industry Risk Contributions */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">{t('component.risk.factor_risk.industry_risk_title')}</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={industryRiskData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={80} />
            <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, t('component.risk.factor_risk.risk_contribution')]} />
            <Bar dataKey="value" fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
