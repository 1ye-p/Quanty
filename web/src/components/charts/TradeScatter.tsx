/**
 * TradeScatter — Trade timing scatter plot with buy/sell triangles.
 *
 * Buy = green triangles pointing up, Sell = red inverted triangles pointing down.
 * Filter buttons: all, profit, loss.
 */
import { useState, useMemo } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  type TooltipProps,
} from 'recharts'

export interface TradePoint {
  date: string         // YYYY-MM-DD
  price: number
  side: 'buy' | 'sell'
  pnl?: number         // P&L for the trade (positive = profit)
  symbol?: string
  quantity?: number
}

interface Props {
  data: TradePoint[]
  title?: string
}

type FilterMode = 'all' | 'profit' | 'loss'

function formatPrice(value: number): string {
  return value.toFixed(2)
}

interface ScatterTooltipPayload {
  payload?: TradePoint
}

function TradeTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const trade = (payload[0] as unknown as ScatterTooltipPayload)?.payload
  if (!trade) return null

  const pnlColor = trade.pnl != null
    ? trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
    : 'text-gray-400'

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-3 text-xs min-w-[160px]">
      {trade.symbol && (
        <p className="font-semibold text-gray-800 mb-1">{trade.symbol}</p>
      )}
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-gray-500">Date</span>
          <span className="text-gray-800 font-medium">{trade.date}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Side</span>
          <span className={`font-medium ${trade.side === 'buy' ? 'text-green-600' : 'text-red-600'}`}>
            {trade.side.toUpperCase()}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Price</span>
          <span className="text-gray-800 font-medium">{formatPrice(trade.price)}</span>
        </div>
        {trade.quantity != null && (
          <div className="flex justify-between">
            <span className="text-gray-500">Qty</span>
            <span className="text-gray-800 font-medium">{trade.quantity}</span>
          </div>
        )}
        {trade.pnl != null && (
          <div className="flex justify-between border-t border-gray-100 pt-1 mt-1">
            <span className="text-gray-500">P&L</span>
            <span className={`font-semibold ${pnlColor}`}>
              {trade.pnl >= 0 ? '+' : ''}{(trade.pnl * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

/** Custom triangle shape for scatter dots */
function BuyTriangle(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props
  const size = 8
  const points = `${cx},${cy - size} ${cx - size},${cy + size} ${cx + size},${cy + size}`
  return <polygon points={points} fill="#16a34a" stroke="#15803d" strokeWidth={1} opacity={0.85} />
}

function SellTriangle(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props
  const size = 8
  const points = `${cx},${cy + size} ${cx - size},${cy - size} ${cx + size},${cy - size}`
  return <polygon points={points} fill="#dc2626" stroke="#b91c1c" strokeWidth={1} opacity={0.85} />
}

export function TradeScatter({ data, title = 'Trade Scatter' }: Props) {
  const [filter, setFilter] = useState<FilterMode>('all')

  const { buys, sells } = useMemo(() => {
    let filtered = data
    if (filter === 'profit') {
      filtered = data.filter(t => t.pnl != null && t.pnl >= 0)
    } else if (filter === 'loss') {
      filtered = data.filter(t => t.pnl != null && t.pnl < 0)
    }
    return {
      buys: filtered.filter(t => t.side === 'buy'),
      sells: filtered.filter(t => t.side === 'sell'),
    }
  }, [data, filter])

  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
        <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
          No trade data available
        </div>
      </div>
    )
  }

  const filters: { key: FilterMode; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'profit', label: 'Profit' },
    { key: 'loss', label: 'Loss' },
  ]

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
          {filters.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                filter === f.key
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="date"
            type="category"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            allowDuplicatedCategory={false}
          />
          <YAxis
            dataKey="price"
            type="number"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={formatPrice}
            name="Price"
          />
          <ZAxis range={[40, 40]} />
          <Tooltip content={<TradeTooltip />} cursor={false} />
          <Scatter
            name="Buy"
            data={buys}
            shape={<BuyTriangle />}
          />
          <Scatter
            name="Sell"
            data={sells}
            shape={<SellTriangle />}
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-600">
          <svg width="14" height="14" viewBox="0 0 14 14">
            <polygon points="7,1 1,13 13,13" fill="#16a34a" stroke="#15803d" strokeWidth={1} />
          </svg>
          Buy
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-600">
          <svg width="14" height="14" viewBox="0 0 14 14">
            <polygon points="7,13 1,1 13,1" fill="#dc2626" stroke="#b91c1c" strokeWidth={1} />
          </svg>
          Sell
        </div>
      </div>
    </div>
  )
}
