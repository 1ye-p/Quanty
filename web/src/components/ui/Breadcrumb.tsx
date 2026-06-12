import { Link, useLocation } from 'react-router-dom'

const ROUTE_LABELS: Record<string, string> = {
  factors: '因子研究',
  strategies: '策略配置',
  ml: '机器学习',
  backtests: '回测评估',
  optimize: '组合优化',
  risk: '风控管理',
  scoring: '截面打分',
  live: '实盘监控',
  trading: '交易中心',
  news: '消息面',
  datasets: '数据集',
  knowledge: '知识库',
  advisor: 'AI 助手',
  alerts: '告警中心',
  tasks: '任务中心',
  pipeline: '自动化管道',
}

export function Breadcrumb() {
  const location = useLocation()
  const crumbs = location.pathname.split('/').filter(Boolean)

  if (crumbs.length === 0) return null

  return (
    <nav className="flex items-center gap-1 text-xs text-gray-400 mb-4">
      <Link to="/" className="hover:text-gray-600 transition-colors">首页</Link>
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1">
          <span>/</span>
          <span className={i === crumbs.length - 1 ? 'text-gray-700 font-medium' : 'hover:text-gray-600'}>
            {ROUTE_LABELS[crumb] || crumb}
          </span>
        </span>
      ))}
    </nav>
  )
}
