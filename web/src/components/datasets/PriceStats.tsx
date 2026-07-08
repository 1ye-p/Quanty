import type { PriceStats as PriceStatsType } from '@/lib/api/market'

interface PriceStatsProps {
  stats: PriceStatsType
}

export function PriceStats({ stats }: PriceStatsProps) {
  const changeColor = stats.change_pct >= 0 ? 'text-green-600' : 'text-red-600'
  const changeSign = stats.change_pct >= 0 ? '+' : ''

  return (
    <div className="grid grid-cols-5 gap-3">
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-500 mb-1">最新价</div>
        <div className="text-lg font-semibold">{stats.latest_price.toFixed(2)}</div>
      </div>
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-500 mb-1">涨跌幅</div>
        <div className={`text-lg font-semibold ${changeColor}`}>
          {changeSign}{(stats.change_pct * 100).toFixed(2)}%
        </div>
      </div>
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-500 mb-1">52周最高</div>
        <div className="text-lg font-semibold">{stats.high_52w.toFixed(2)}</div>
      </div>
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-500 mb-1">52周最低</div>
        <div className="text-lg font-semibold">{stats.low_52w.toFixed(2)}</div>
      </div>
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-500 mb-1">平均成交量</div>
        <div className="text-lg font-semibold">{(stats.avg_volume / 1e6).toFixed(2)}M</div>
      </div>
    </div>
  )
}
