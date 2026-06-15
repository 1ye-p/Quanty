import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scoringApi } from '@/lib/api/scoring'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface SnapshotScores {
  run_id: string
  created_at: string
  config_name: string
  scores: Map<string, { score: number; rank: number }>
}

export function ScoreHistory() {
  const [selectedAsset, setSelectedAsset] = useState<string>('')
  const [selectedSnapshots, setSelectedSnapshots] = useState<string[]>([])

  const { data: snapshotsData, isLoading: snapshotsLoading } = useQuery({
    queryKey: ['scoring', 'snapshots', 'history'],
    queryFn: () => scoringApi.listSnapshots(50),
    staleTime: 60_000,
  })

  const completedSnapshots = useMemo(() => {
    if (!snapshotsData?.items) return []
    return snapshotsData.items.filter(s => s.status === 'completed')
  }, [snapshotsData])

  const last5Snapshots = useMemo(() => {
    return completedSnapshots.slice(0, 5)
  }, [completedSnapshots])

  const { data: snapshotScores, isLoading: scoresLoading } = useQuery({
    queryKey: ['scoring', 'history', 'scores', selectedSnapshots],
    queryFn: async () => {
      const results: SnapshotScores[] = []
      for (const runId of selectedSnapshots) {
        const snapshot = completedSnapshots.find(s => s.run_id === runId)
        if (!snapshot) continue
        try {
          const data = await scoringApi.getResult(runId, 0, 10000)
          const scoresMap = new Map<string, { score: number; rank: number }>()
          for (const r of data.results) {
            if (r.score !== null && r.rank !== null) {
              scoresMap.set(r.asset_id, { score: r.score, rank: r.rank })
            }
          }
          results.push({
            run_id: runId,
            created_at: snapshot.created_at || '',
            config_name: snapshot.config_name,
            scores: scoresMap,
          })
        } catch (e) {
          console.error(`Failed to load scores for ${runId}`, e)
        }
      }
      return results
    },
    enabled: selectedSnapshots.length > 0,
    staleTime: 120_000,
  })

  const allAssets = useMemo(() => {
    if (!snapshotScores || snapshotScores.length === 0) return []
    const assetSet = new Set<string>()
    for (const ss of snapshotScores) {
      for (const assetId of ss.scores.keys()) {
        assetSet.add(assetId)
      }
    }
    return Array.from(assetSet).sort()
  }, [snapshotScores])

  const trendData = useMemo(() => {
    if (!snapshotScores || !selectedAsset) return []
    return snapshotScores
      .slice()
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .map(ss => {
        const entry = ss.scores.get(selectedAsset)
        return {
          date: ss.created_at.slice(0, 10),
          config: ss.config_name,
          score: entry?.score ?? null,
          rank: entry?.rank ?? null,
        }
      })
      .filter(d => d.score !== null)
  }, [snapshotScores, selectedAsset])

  const rankChangeData = useMemo(() => {
    if (!snapshotScores || snapshotScores.length < 2) return []
    const sorted = snapshotScores.slice().sort((a, b) => a.created_at.localeCompare(b.created_at))
    const latest = sorted[sorted.length - 1]
    if (!latest) return []

    const rankedAssets = Array.from(latest.scores.entries())
      .sort((a, b) => (a[1].rank ?? Infinity) - (b[1].rank ?? Infinity))
      .slice(0, 10)

    return rankedAssets.map(([assetId, latestEntry]) => {
      const row: Record<string, unknown> = { asset_id: assetId, latest_rank: latestEntry.rank }
      for (let i = 0; i < sorted.length; i++) {
        const ss = sorted[i]
        const entry = ss.scores.get(assetId)
        row[`snap_${i}`] = entry?.rank ?? '-'
        row[`snap_${i}_label`] = ss.created_at.slice(0, 10)
      }
      const prev = sorted[sorted.length - 2]
      const prevEntry = prev?.scores.get(assetId)
      row['rank_change'] = prevEntry ? (prevEntry.rank ?? 0) - (latestEntry.rank ?? 0) : null
      return row
    })
  }, [snapshotScores])

  const handleToggleSnapshot = (runId: string) => {
    setSelectedSnapshots(prev =>
      prev.includes(runId) ? prev.filter(id => id !== runId) : [...prev, runId]
    )
  }

  const handleSelectLast5 = () => {
    setSelectedSnapshots(last5Snapshots.map(s => s.run_id))
  }

  if (snapshotsLoading) {
    return (
      <div className="card">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-100 rounded w-1/4" />
          <div className="h-40 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (completedSnapshots.length === 0) {
    return (
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">历史对比</h2>
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">暂无历史打分记录</p>
          <p className="text-sm mt-2">运行打分后即可在此查看历史对比</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Snapshot selector */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">历史快照选择</h2>
          <button
            onClick={handleSelectLast5}
            className="text-xs text-brand-600 hover:text-brand-700"
          >
            选择最近5次
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {completedSnapshots.map(s => (
            <button
              key={s.run_id}
              onClick={() => handleToggleSnapshot(s.run_id)}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                selectedSnapshots.includes(s.run_id)
                  ? 'bg-brand-100 border-brand-500 text-brand-700'
                  : 'bg-white border-gray-300 text-gray-600 hover:border-brand-400'
              }`}
            >
              <span className="font-mono">{s.created_at?.slice(0, 10)}</span>
              <span className="ml-1 text-gray-500">{s.config_name}</span>
              <span className="ml-1 text-gray-400">({s.start_date}~{s.end_date})</span>
            </button>
          ))}
        </div>
        {selectedSnapshots.length < 2 && (
          <p className="text-xs text-gray-400 mt-2">请选择至少2个快照进行对比</p>
        )}
      </div>

      {/* Asset selector + trend chart */}
      {selectedSnapshots.length >= 2 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">资产得分趋势</h2>

          {scoresLoading ? (
            <div className="animate-pulse space-y-2">
              <div className="h-8 bg-gray-100 rounded w-1/3" />
              <div className="h-64 bg-gray-100 rounded" />
            </div>
          ) : (
            <>
              <div className="mb-4">
                <label className="block text-sm text-gray-600 mb-2">选择资产</label>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                  {allAssets.slice(0, 100).map(asset => (
                    <button
                      key={asset}
                      onClick={() => setSelectedAsset(asset)}
                      className={`px-2 py-1 rounded text-xs border transition-colors ${
                        selectedAsset === asset
                          ? 'bg-brand-500 text-white border-brand-500'
                          : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
                      }`}
                    >
                      {asset}
                    </button>
                  ))}
                  {allAssets.length > 100 && (
                    <span className="text-xs text-gray-400 py-1">...共 {allAssets.length} 个资产</span>
                  )}
                </div>
              </div>

              {selectedAsset && trendData.length > 0 ? (
                <div>
                  <h3 className="text-sm text-gray-600 mb-2">
                    {selectedAsset} 得分趋势
                  </h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={trendData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(value: number, name: string) => {
                          if (name === 'score') return [value?.toFixed(4), '得分']
                          if (name === 'rank') return [value, '排名']
                          return [value, name]
                        }}
                        labelFormatter={(label: string) => `日期: ${label}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        activeDot={{ r: 6 }}
                        name="score"
                      />
                      <Line
                        type="monotone"
                        dataKey="rank"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        yAxisId="rank"
                        name="rank"
                      />
                      <YAxis yAxisId="rank" orientation="right" tick={{ fontSize: 11 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : selectedAsset ? (
                <div className="text-center py-8 text-gray-400">
                  该资产在选中的快照中无数据
                </div>
              ) : (
                <div className="text-center py-8 text-gray-400">
                  请从上方选择一个资产查看趋势
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Rank change table */}
      {selectedSnapshots.length >= 2 && snapshotScores && snapshotScores.length >= 2 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">排名变动（Top 10）</h2>
          {scoresLoading ? (
            <div className="animate-pulse space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 rounded" />
              ))}
            </div>
          ) : rankChangeData.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-2 pr-4">资产</th>
                    {last5Snapshots.slice(0, selectedSnapshots.length).map((s, i) => (
                      <th key={i} className="py-2 px-2 text-center">
                        <span className="text-xs text-gray-400">{s.created_at?.slice(5, 10)}</span>
                      </th>
                    ))}
                    <th className="py-2 pl-4 text-center">排名变化</th>
                  </tr>
                </thead>
                <tbody>
                  {rankChangeData.map((row) => (
                    <tr key={String(row.asset_id)} className="border-b hover:bg-gray-50">
                      <td className="py-2 pr-4 font-mono text-xs">{String(row.asset_id)}</td>
                      {last5Snapshots.slice(0, selectedSnapshots.length).map((_, i) => (
                        <td key={i} className="py-2 px-2 text-center text-xs">
                          {String(row[`snap_${i}`] ?? '-')}
                        </td>
                      ))}
                      <td className="py-2 pl-4 text-center">
                        {row.rank_change !== null && row.rank_change !== undefined ? (
                          <span className={`text-xs font-medium ${
                            Number(row.rank_change) > 0 ? 'text-green-600' :
                            Number(row.rank_change) < 0 ? 'text-red-500' :
                            'text-gray-500'
                          }`}>
                            {Number(row.rank_change) > 0 ? `+${String(row.rank_change)}` : String(row.rank_change)}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              无法计算排名变动
            </div>
          )}
        </div>
      )}
    </div>
  )
}
