import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { riskApi } from '@/lib/api/risk'
import { extendedQueryKeys } from '@/lib/queryKeys'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'

const STYLE_FACTORS = ['market_cap', 'value', 'momentum', 'volatility', 'turnover', 'quality']

const STYLE_LABELS: Record<string, string> = {
  market_cap: '市值',
  value: '价值',
  momentum: '动量',
  volatility: '波动率',
  turnover: '换手率',
  quality: '质量',
}

interface FactorRiskPanelProps {
  weights: Record<string, number>
}

export const FactorRiskPanel: React.FC<FactorRiskPanelProps> = ({ weights }) => {
  const weightsJson = useMemo(() => JSON.stringify(weights), [weights])

  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.risk.factorDecomposition(weightsJson),
    queryFn: () => riskApi.getFactorDecomposition({ weights_json: weightsJson }),
    enabled: Object.keys(weights).length > 0,
  })

  if (!Object.keys(weights).length) {
    return <div className="text-center py-8 text-gray-400">暂无持仓权重数据</div>
  }
  if (isLoading) return <div className="text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="text-center py-8 text-red-500">加载失败: {error.message}</div>
  if (!data) return null

  const { style_exposures, risk_decomposition } = data
  const {
    total_risk, factor_risk, idiosyncratic_risk, factor_risk_pct,
    style_risk_contributions, industry_risk_contributions,
  } = risk_decomposition

  // Radar chart data
  const radarData = STYLE_FACTORS.map(f => ({
    factor: STYLE_LABELS[f] ?? f,
    exposure: Math.round((style_exposures[f] ?? 0) * 10000) / 100,
  }))

  // Style risk contribution data (sorted desc)
  const styleRiskData = Object.entries(style_risk_contributions)
    .map(([k, v]) => ({ name: STYLE_LABELS[k] ?? k, value: v }))
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
          <div className="text-sm text-gray-500">总风险</div>
          <div className="text-2xl font-semibold">{(total_risk * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">因子风险</div>
          <div className="text-2xl font-semibold text-indigo-600">{(factor_risk * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">因子风险占比</div>
          <div className="text-2xl font-semibold text-indigo-600">{Number(factor_risk_pct).toFixed(1)}%</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">特异性风险</div>
          <div className="text-2xl font-semibold text-gray-800">{(idiosyncratic_risk * 100).toFixed(2)}%</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Style Exposure Radar */}
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-medium text-gray-800 mb-4">风格暴露雷达图</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
              <PolarGrid />
              <PolarAngleAxis dataKey="factor" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis tick={{ fontSize: 10 }} />
              <Radar name="暴露" dataKey="exposure" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              <Tooltip formatter={(v: number) => [`${v}%`, '暴露']} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Style Risk Contributions */}
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-medium text-gray-800 mb-4">风格风险贡献</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={styleRiskData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={60} />
              <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, '风险贡献']} />
              <Bar dataKey="value" fill="#818cf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Industry Risk Contributions */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">行业风险贡献 (Top 10)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={industryRiskData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={80} />
            <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, '风险贡献']} />
            <Bar dataKey="value" fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
