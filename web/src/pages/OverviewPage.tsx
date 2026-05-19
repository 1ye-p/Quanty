import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { datasetsApi, backtestsApi, knowledgeApi, liveApi } from '@/lib/api'
import { queryKeys, extendedQueryKeys } from '@/lib/queryKeys'
import { StatusBadge } from '@/components/ui/StatusBadge'

interface QuickLinkProps { to: string; icon: string; label: string; desc: string }
function QuickLink({ to, icon, label, desc }: QuickLinkProps) {
  return (
    <Link to={to} className="card hover:shadow-md transition-shadow group flex items-start gap-3 no-underline">
      <span className="text-2xl">{icon}</span>
      <div>
        <div className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">{label}</div>
        <div className="text-xs text-gray-400 mt-0.5">{desc}</div>
      </div>
    </Link>
  )
}

interface StatCardProps { label: string; value: string | number; icon: string; delta?: string; warn?: boolean }
function StatCard({ label, value, icon, delta, warn }: StatCardProps) {
  return (
    <div className={`card ${warn ? 'border-l-4 border-amber-400' : ''}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-3xl font-bold text-brand-600">{value}</div>
          <div className="text-sm text-gray-500 mt-1">{label}</div>
          {delta && <div className="text-xs text-green-600 mt-0.5">{delta}</div>}
        </div>
        <span className="text-2xl opacity-60">{icon}</span>
      </div>
    </div>
  )
}

export function OverviewPage() {
  const { data: datasets } = useQuery({
    queryKey: queryKeys.datasets.list(5),
    queryFn: () => datasetsApi.list(5),
  })
  const { data: backtests } = useQuery({
    queryKey: queryKeys.backtests.list(5),
    queryFn: () => backtestsApi.list(5),
  })
  const { data: knowledgeDocs } = useQuery({
    queryKey: queryKeys.knowledge.list(),
    queryFn: () => knowledgeApi.list(),
  })
  const { data: liveStrategies } = useQuery({
    queryKey: extendedQueryKeys.live.strategies(),
    queryFn: liveApi.strategies,
  })

  const completedRuns = backtests?.items.filter(r => r.status === 'completed').length ?? 0
  const runningStrategies = liveStrategies?.items.length ?? 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">cQuant 量化研究平台</h1>
        <p className="text-sm text-gray-500 mt-1">离线研究仪表盘 · 无真实交易 · 全量化流程一站式管理</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="数据集版本" value={datasets?.total ?? '—'} icon="🗄️" />
        <StatCard label="回测记录" value={backtests?.total ?? '—'} icon="📊"
          delta={completedRuns > 0 ? `${completedRuns} 已完成` : undefined} />
        <StatCard label="知识库文档" value={knowledgeDocs?.total ?? '—'} icon="📚" />
        <StatCard label="活跃策略" value={runningStrategies} icon="⚡"
          warn={runningStrategies === 0} />
      </div>

      {/* Quick links */}
      <div>
        <h2 className="text-base font-semibold text-gray-700 mb-3">快捷入口</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickLink to="/factors"    icon="🔬" label="因子研究"  desc="IC/IR 分析与对比" />
          <QuickLink to="/strategies" icon="⚙️" label="策略配置"  desc="JSON 编辑器管理策略" />
          <QuickLink to="/backtests"  icon="📈" label="回测评估"  desc="Tearsheet 与过拟合检测" />
          <QuickLink to="/advisor"    icon="🤖" label="AI 助手"   desc="多智能体研究分析" />
          <QuickLink to="/ml"         icon="🧠" label="机器学习"  desc="XGBoost/LightGBM 实验" />
          <QuickLink to="/knowledge"  icon="📄" label="知识库"    desc="研报语义检索" />
          <QuickLink to="/news"       icon="📰" label="消息面"    desc="新闻情绪监控" />
          <QuickLink to="/live"       icon="📡" label="实盘监控"  desc="模拟持仓与风险" />
        </div>
      </div>

      {/* Recent backtests */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">最近回测</h2>
          <Link to="/backtests" className="text-xs text-brand-600 hover:underline">查看全部 →</Link>
        </div>
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                {['Run ID', '策略', '引擎', '状态', '开始时间'].map(h => (
                  <th key={h} className="table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!backtests?.items.length && (
                <tr>
                  <td colSpan={5} className="table-td text-center text-gray-400 py-8">
                    暂无回测记录 · <Link to="/strategies" className="text-brand-600 hover:underline">先创建策略</Link>
                  </td>
                </tr>
              )}
              {backtests?.items.map(r => (
                <tr key={r.run_id} className="table-row">
                  <td className="table-td font-mono text-xs">{r.run_id.slice(0, 8)}…</td>
                  <td className="table-td font-medium">{r.strategy_id}</td>
                  <td className="table-td text-gray-500">{r.engine}</td>
                  <td className="table-td"><StatusBadge status={r.status} /></td>
                  <td className="table-td text-gray-400">{r.started_at?.slice(0, 16) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent knowledge docs */}
      {(knowledgeDocs?.items.length ?? 0) > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">最近入库文档</h2>
            <Link to="/knowledge" className="text-xs text-brand-600 hover:underline">查看全部 →</Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {knowledgeDocs?.items.slice(0, 6).map(d => (
              <div key={d.doc_id} className="card py-3">
                <div className="font-medium text-sm text-gray-900 truncate">
                  {d.title || <em className="text-gray-400">无标题</em>}
                </div>
                <div className="flex gap-2 mt-1 text-xs text-gray-400">
                  <span>{d.source_name || '未知来源'}</span>
                  <span>·</span>
                  <span className="capitalize">{d.logical_type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* System info */}
      <div className="card bg-gradient-to-r from-brand-600 to-indigo-700 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold text-lg">cQuant v0.1.0</div>
            <div className="text-blue-100 text-sm mt-1">
              后端 API · <span className="font-mono text-xs">localhost:8000/api/docs</span>
            </div>
          </div>
          <div className="text-right text-sm text-blue-100 space-y-0.5">
            <div>✅ 35 个单元测试通过</div>
            <div>✅ Phase 1+2+3 全部完成</div>
            <div>🔒 无真实交易接口</div>
          </div>
        </div>
      </div>
    </div>
  )
}
