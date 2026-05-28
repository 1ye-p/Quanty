import { useState, useEffect } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { mlApi, backtestsApi, scoringApi, alertsApi } from '@/lib/api'

const NAV_ICONS: Record<string, string> = {
  '/factors':    '🔬',
  '/strategies': '⚙️',
  '/ml':         '🧠',
  '/backtests':  '📈',
  '/optimize':   '⚖️',
  '/risk':       '🛡',
  '/scoring':    '🎯',
  '/live':       '📡',
  '/trading':    '💹',
  '/news':       '📰',
  '/datasets':   '🗄️',
  '/knowledge':  '📚',
  '/advisor':    '🤖',
  '/':           '🏠',
  '/alerts':    '🔔',
}

const NAV_GROUPS = [
  {
    label: '研究工具',
    items: [
      { to: '/factors',    label: '因子研究' },
      { to: '/strategies', label: '策略配置' },
      { to: '/ml',         label: '机器学习' },
      { to: '/backtests',  label: '回测评估' },
      { to: '/optimize',   label: '组合优化' },
      { to: '/risk',       label: '风控管理' },
      { to: '/scoring',    label: '截面打分' },
    ],
  },
  {
    label: '数据 & 监控',
    items: [
      { to: '/live',     label: '实盘监控' },
      { to: '/trading',  label: '交易中心' },
      { to: '/news',     label: '消息面' },
      { to: '/datasets', label: '数据集' },
    ],
  },
  {
    label: '知识 & AI',
    items: [
      { to: '/knowledge', label: '知识库' },
      { to: '/advisor',   label: 'AI 分析助手' },
    ],
  },
  {
    label: '系统',
    items: [
      { to: '/',       label: '总览' },
      { to: '/alerts', label: '告警中心' },
    ],
  },
]

// Dev-time guard: warn if any nav route is missing from NAV_ICONS
if (import.meta.env.DEV) {
  NAV_GROUPS.flatMap(g => g.items).forEach(({ to, label }) => {
    if (!(to in NAV_ICONS)) {
      console.warn(`[AppLayout] Missing icon for nav route "${to}" (${label}). Add an entry to NAV_ICONS.`)
    }
  })
}

export function AppLayout() {
  // 轮询各模块运行中任务数量
  const { data: mlJobs } = useQuery({
    queryKey: ['layout', 'ml-running'],
    queryFn: () => mlApi.experiments(100),
    refetchInterval: 10_000,
    select: (d) => d.items?.filter(
      (e: { status: string }) => e.status === 'running' || e.status === 'pending'
    ).length ?? 0,
  })

  const { data: btJobs } = useQuery({
    queryKey: ['layout', 'bt-running'],
    queryFn: () => backtestsApi.list(0, 50),
    refetchInterval: 10_000,
    select: (d) => d.items?.filter(
      (r: { status: string }) => r.status === 'running' || r.status === 'pending'
    ).length ?? 0,
  })

  const { data: scoringJobs } = useQuery({
    queryKey: ['layout', 'scoring-running'],
    queryFn: () => scoringApi.listSnapshots(20),
    refetchInterval: 10_000,
    select: (d) => d.items?.filter(
      (s: { status: string }) => s.status === 'running' || s.status === 'pending'
    ).length ?? 0,
  })

  const runningBadges: Record<string, number> = {}
  if ((mlJobs ?? 0) > 0) runningBadges['/ml'] = mlJobs as number
  if ((btJobs ?? 0) > 0) runningBadges['/backtests'] = btJobs as number
  if ((scoringJobs ?? 0) > 0) runningBadges['/scoring'] = scoringJobs as number

  const [taskDropdownOpen, setTaskDropdownOpen] = useState(false)

  // Detailed running task queries for topbar
  const { data: mlRunning } = useQuery({
    queryKey: ['layout', 'ml-running-details'],
    queryFn: () => mlApi.experiments(50),
    refetchInterval: 10_000,
    select: (d) => (d.items ?? [])
      .filter((e: { status: string }) => e.status === 'running' || e.status === 'pending')
      .map((e: { run_id: string; status: string; started_at?: number | string; trainer_name?: string }) => ({
        type: 'ML训练',
        id: e.run_id.slice(0, 10),
        status: e.status,
        startedAt: e.started_at,
        detail: e.trainer_name ?? '',
      })),
  })

  const { data: btRunning } = useQuery({
    queryKey: ['layout', 'bt-running-details'],
    queryFn: () => backtestsApi.list(0, 50),
    refetchInterval: 10_000,
    select: (d) => (d.items ?? [])
      .filter((r: { status: string }) => r.status === 'running' || r.status === 'pending')
      .map((r: { run_id: string; status: string; started_at?: string; strategy_id?: string }) => ({
        type: '回测',
        id: r.run_id.slice(0, 10),
        status: r.status,
        startedAt: r.started_at,
        detail: r.strategy_id ?? '',
      })),
  })

  const allRunningTasks = [...(mlRunning ?? []), ...(btRunning ?? [])]
  const runningCount = allRunningTasks.length

  function elapsedStr(startedAt: string | number | undefined): string {
    if (!startedAt) return ''
    const start = typeof startedAt === 'number' ? startedAt : new Date(startedAt).getTime()
    const elapsed = Math.floor((Date.now() - start) / 1000)
    if (elapsed < 60) return `${elapsed}s`
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
    return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`
  }

  useEffect(() => {
    if (!taskDropdownOpen) return
    const handler = () => setTaskDropdownOpen(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [taskDropdownOpen])

  const { data: alertUnread } = useQuery({
    queryKey: ['alerts', 'unread-count'],
    queryFn: () => alertsApi.history(true, 1),
    refetchInterval: 60_000,
    select: (d) => d.unread_count,
  })

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem('sidebar_collapsed') === 'true' } catch { return false }
  })

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev
      try { localStorage.setItem('sidebar_collapsed', String(next)) } catch {}
      return next
    })
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <nav className={`${
        collapsed ? 'w-12' : 'w-56'
      } bg-brand-600 text-gray-100 flex flex-col flex-shrink-0 sticky top-0 h-screen overflow-y-auto transition-[width] duration-200`}>

        {collapsed ? (
          <button
            onClick={toggleCollapsed}
            className="p-3 hover:bg-white/10 text-center text-lg w-full"
            title="展开侧边栏"
          >
            ☰
          </button>
        ) : (
          <div className="flex items-center justify-between px-5 py-5">
            <Link to="/" className="text-white font-bold text-lg hover:text-blue-100 transition-colors">
              cQuant
            </Link>
            <button
              onClick={toggleCollapsed}
              className="text-blue-200 hover:text-white text-sm"
              title="折叠侧边栏"
            >
              ◀
            </button>
          </div>
        )}

        <div className="flex-1 px-2 pb-4 space-y-4">
          {NAV_GROUPS.map(group => (
            <div key={group.label}>
              {!collapsed && (
                <div className="px-2 py-1 text-xs font-semibold text-blue-200 uppercase tracking-wider">
                  {group.label}
                </div>
              )}
              <ul className="space-y-0.5">
                {group.items.map(({ to, label }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={to === '/'}
                      title={collapsed ? label : undefined}
                      className={({ isActive }) =>
                        `flex items-center ${collapsed ? 'justify-center px-2' : 'px-3'} py-2 rounded-lg text-sm transition-colors ${
                          isActive
                            ? 'bg-white/20 text-white font-semibold'
                            : 'text-blue-100 hover:bg-white/10 hover:text-white'
                        }`
                      }
                    >
                      {collapsed ? (
                        <span className="relative text-base">
                          {NAV_ICONS[to] ?? label[0]}
                          {runningBadges[to] ? (
                            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-blue-300 animate-pulse" />
                          ) : to === '/alerts' && (alertUnread ?? 0) > 0 ? (
                            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 text-[7px] bg-red-500 text-white rounded-full flex items-center justify-center">
                              {(alertUnread ?? 0) > 9 ? '9+' : alertUnread}
                            </span>
                          ) : null}
                        </span>
                      ) : (
                        <>
                          <span className="flex-1">{label}</span>
                          {to === '/alerts' && (alertUnread ?? 0) > 0 ? (
                            <span className="px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full min-w-[18px] text-center flex-shrink-0">
                              {alertUnread}
                            </span>
                          ) : runningBadges[to] ? (
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-300 animate-pulse flex-shrink-0" />
                          ) : null}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </nav>

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Topbar */}
          <header className="h-10 bg-white border-b border-gray-200 flex items-center justify-end px-4 flex-shrink-0 relative z-10">
            {runningCount > 0 ? (
              <div className="relative">
                <button
                  onClick={(e) => { e.stopPropagation(); setTaskDropdownOpen(o => !o) }}
                  className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100"
                >
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                  <span className="font-medium">⚙ {runningCount} 个任务运行中</span>
                  <span className="text-xs text-gray-400">▾</span>
                </button>
                {taskDropdownOpen && (
                  <div
                    className="absolute right-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded-xl shadow-lg z-50"
                    onClick={e => e.stopPropagation()}
                  >
                    <div className="px-3 py-2 border-b text-xs font-semibold text-gray-500 uppercase">
                      进行中的任务
                    </div>
                    <ul className="divide-y divide-gray-100 max-h-64 overflow-y-auto">
                      {allRunningTasks.map((task, i) => (
                        <li key={i} className="px-3 py-2 flex items-center justify-between">
                          <div>
                            <span className="text-xs font-medium text-gray-700">{task.type}</span>
                            <span className="ml-2 font-mono text-xs text-gray-400">{task.id}…</span>
                            {task.detail && (
                              <div className="text-xs text-gray-500 truncate max-w-[160px]">{task.detail}</div>
                            )}
                          </div>
                          <div className="text-right flex-shrink-0 ml-2">
                            <span className="text-xs text-gray-400">
                              {elapsedStr(task.startedAt)}
                            </span>
                            <div className="text-xs text-blue-500 mt-0.5">
                              {task.status}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <div className="px-3 py-2 border-t text-xs text-gray-400 text-center">
                      每10秒自动刷新
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <span className="text-xs text-gray-400">无运行中任务</span>
            )}
          </header>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto p-8 bg-gray-50">
            <Outlet />
          </main>
        </div>
    </div>
  )
}
