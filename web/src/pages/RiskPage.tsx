import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation } from '@tanstack/react-query'
import { riskApi } from '@/lib/api'
import type { PolicyInfo, SizerInfo, RiskCheckResult } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { PositionRiskDashboard } from '@/components/risk/PositionRiskDashboard'
import { RiskEventHistory } from '@/components/risk/RiskEventHistory'
import { FactorRiskPanel } from '@/components/risk/FactorRiskPanel'

export function RiskPage() {
  const { t } = useTranslation()
  // Tab navigation
  const [activeTab, setActiveTab] = useState('check')

  const tabs = [
    { id: 'check', label: t('page.risk.tab.check') },
    { id: 'positions', label: t('page.risk.tab.positions') },
    { id: 'factor', label: t('page.risk.tab.factor') },
    { id: 'events', label: t('page.risk.tab.events') },
  ]

  // Risk check form state
  const [policyName, setPolicyName] = useState('')
  const [assetId, setAssetId] = useState('')
  const [side, setSide] = useState('buy')
  const [qty, setQty] = useState('100')
  const [price, setPrice] = useState('50')
  const [nav, setNav] = useState('1000000')
  const [policyParams, setPolicyParams] = useState<Record<string, string>>({})
  const [checkResult, setCheckResult] = useState<RiskCheckResult | null>(null)

  const { data: policies } = useQuery({
    queryKey: extendedQueryKeys.risk.policies(),
    queryFn: riskApi.policies,
  })

  const { data: sizers } = useQuery({
    queryKey: extendedQueryKeys.risk.sizers(),
    queryFn: riskApi.sizers,
  })

  const { data: portfolioRisk } = useQuery({
    queryKey: extendedQueryKeys.risk.positions(),
    queryFn: () => riskApi.getPositions(),
    enabled: activeTab === 'factor',
  })

  const positionWeights = useMemo(() => {
    if (!portfolioRisk?.positions) return {}
    const w: Record<string, number> = {}
    for (const p of portfolioRisk.positions) {
      if (p.weight) w[p.asset_id] = p.weight
    }
    return w
  }, [portfolioRisk?.positions])

  const checkMutation = useMutation({
    mutationFn: riskApi.check,
    onSuccess: (data) => setCheckResult(data),
  })

  const selectedPolicy = policies?.find(p => p.name === policyName)

  const handleCheck = () => {
    if (!policyName || !assetId) return
    const params: Record<string, unknown> = {}
    if (selectedPolicy) {
      for (const p of selectedPolicy.params) {
        const val = policyParams[p.key]
        if (val !== undefined && val !== '') {
          const num = Number(val)
          params[p.key] = isNaN(num) ? val : num
        }
      }
    }
    checkMutation.mutate({
      policy_name: policyName,
      params: Object.keys(params).length > 0 ? params : undefined,
      asset_id: assetId,
      side,
      qty: Number(qty),
      price: Number(price),
      nav: Number(nav),
    })
  }

  const decisionColor = (d: string) => {
    if (d === 'approved') return 'text-green-700 bg-green-50'
    if (d === 'clipped') return 'text-yellow-700 bg-yellow-50'
    return 'text-red-700 bg-red-50'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t('page.risk.title')}</h1>

      <div className="flex gap-1 border-b mb-6">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'check' && (
      <>
      <div className="grid grid-cols-2 gap-6">
        {/* Policies List */}
        <div className="bg-white rounded-xl shadow-sm border p-5">
          <h2 className="font-semibold text-gray-800 mb-3">{t('page.risk.section.policies')}</h2>
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {policies?.map(p => (
              <PolicyCard key={p.name} policy={p} />
            ))}
            {!policies && <div className="text-gray-400 text-sm">{t('common.loading')}</div>}
          </div>
        </div>

        {/* Sizers List */}
        <div className="bg-white rounded-xl shadow-sm border p-5">
          <h2 className="font-semibold text-gray-800 mb-3">{t('page.risk.section.sizers')}</h2>
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {sizers?.map(s => (
              <SizerCard key={s.name} sizer={s} />
            ))}
            {!sizers && <div className="text-gray-400 text-sm">{t('common.loading')}</div>}
          </div>
        </div>
      </div>

      {/* Risk Check Tool */}
      <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
        <h2 className="font-semibold text-gray-800">{t('page.risk.section.check_tool')}</h2>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.policy')}</label>
            <select className="input w-full" value={policyName}
              onChange={e => { setPolicyName(e.target.value); setPolicyParams({}); setCheckResult(null) }}>
              <option value="">{t('page.risk.placeholder.select_policy')}</option>
              {policies?.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.asset_id')}</label>
            <input className="input w-full" value={assetId} onChange={e => setAssetId(e.target.value)}
              placeholder="600519.SSE" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.side')}</label>
            <select className="input w-full" value={side} onChange={e => setSide(e.target.value)}>
              <option value="buy">{t('page.risk.option.buy')}</option>
              <option value="sell">{t('page.risk.option.sell')}</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.qty')}</label>
            <input type="number" className="input w-full" value={qty}
              onChange={e => setQty(e.target.value)} min={1} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.price')}</label>
            <input type="number" className="input w-full" value={price}
              onChange={e => setPrice(e.target.value)} min={0} step={0.01} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('page.risk.field.nav')}</label>
            <input type="number" className="input w-full" value={nav}
              onChange={e => setNav(e.target.value)} min={0} />
          </div>
        </div>

        {/* Policy params */}
        {selectedPolicy && selectedPolicy.params.length > 0 && (
          <div className="border rounded-lg p-3 bg-gray-50">
            <div className="text-xs font-medium text-gray-600 mb-2">{t('page.risk.section.policy_params')}</div>
            <div className="grid grid-cols-3 gap-2">
              {selectedPolicy.params.map(p => (
                <div key={p.key}>
                  <label className="text-xs text-gray-500">{p.description}</label>
                  <input className="input w-full" placeholder={String(p.default)}
                    value={policyParams[p.key] ?? ''}
                    onChange={e => setPolicyParams(prev => ({ ...prev, [p.key]: e.target.value }))} />
                </div>
              ))}
            </div>
          </div>
        )}

        <button className="btn-primary" onClick={handleCheck}
          disabled={checkMutation.isPending || !policyName || !assetId}>
          {checkMutation.isPending ? t('page.risk.action.checking') : t('page.risk.action.check')}
        </button>

        {checkMutation.isError && (
          <div className="text-red-600 text-sm">{String(checkMutation.error)}</div>
        )}

        {/* Result */}
        {checkResult && (
          <div className={`rounded-lg p-4 ${decisionColor(checkResult.decision)}`}>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-lg font-bold uppercase">{checkResult.decision}</span>
              <span className="text-sm">
                {t('page.risk.result.original')}: {checkResult.original_qty} → {t('page.risk.result.approved')}: {checkResult.approved_qty}
              </span>
            </div>
            {checkResult.reasons.length > 0 && (
              <ul className="text-sm list-disc list-inside space-y-1">
                {checkResult.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
      </>
      )}

      {activeTab === 'positions' && <PositionRiskDashboard />}
      {activeTab === 'factor' && <FactorRiskPanel weights={positionWeights} />}
      {activeTab === 'events' && <RiskEventHistory />}
    </div>
  )
}

function PolicyCard({ policy }: { policy: PolicyInfo }) {
  return (
    <div className="border rounded-lg p-3 hover:bg-gray-50 transition-colors">
      <div className="font-medium text-gray-800 text-sm">{policy.name}</div>
      <div className="text-xs text-gray-500 mt-1">{policy.description}</div>
      {policy.params.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {policy.params.map(p => (
            <span key={p.key} className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">
              {p.key}: {String(p.default)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function SizerCard({ sizer }: { sizer: SizerInfo }) {
  return (
    <div className="border rounded-lg p-3 hover:bg-gray-50 transition-colors">
      <div className="font-medium text-gray-800 text-sm">{sizer.name}</div>
      <div className="text-xs text-gray-500 mt-1">{sizer.description}</div>
      {sizer.params.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {sizer.params.map(p => (
            <span key={p.key} className="text-xs bg-green-50 text-green-700 px-1.5 py-0.5 rounded">
              {p.key}: {String(p.default)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
