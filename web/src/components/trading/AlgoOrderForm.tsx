import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { tradingApi, type AlgoOrderParams } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { detectExchange } from '@/lib/utils'

type OrderType = 'market' | 'limit' | 'twap' | 'vwap'

interface AlgoOrderFormProps {
  broker?: string
  onSubmitted?: () => void
}

export function AlgoOrderForm({ broker = 'paper', onSubmitted }: AlgoOrderFormProps) {
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [qty, setQty] = useState('1000')
  const [orderType, setOrderType] = useState<OrderType>('market')
  const [limitPrice, setLimitPrice] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [numSlices, setNumSlices] = useState('10')
  const [lookbackDays, setLookbackDays] = useState('5')

  const queryClient = useQueryClient()

  const orderMutation = useMutation({
    mutationFn: (body: AlgoOrderParams) => tradingApi.placeAlgoOrder(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.orders(broker) })
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.account(broker) })
      // Reset form
      setSymbol('')
      setQty('1000')
      setLimitPrice('')
      setStartTime('')
      setEndTime('')
      onSubmitted?.()
    },
  })

  const isAlgoType = orderType === 'twap' || orderType === 'vwap'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!symbol || !qty) return

    const exchange = detectExchange(symbol)
    const params: AlgoOrderParams = {
      asset_id: `${exchange}:${symbol}`,
      side,
      total_qty: parseInt(qty),
      order_type: orderType,
      broker,
    }

    if (orderType === 'limit' && limitPrice) {
      params.limit_price = parseFloat(limitPrice)
    }
    if (isAlgoType) {
      if (startTime) params.start_time = startTime
      if (endTime) params.end_time = endTime
    }
    if (orderType === 'twap') {
      params.num_slices = parseInt(numSlices) || 10
    }
    if (orderType === 'vwap') {
      params.lookback_days = parseInt(lookbackDays) || 5
    }

    orderMutation.mutate(params)
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h2 className="font-semibold text-gray-800 mb-4">算法下单</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Symbol */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">股票代码</label>
          <input
            type="text"
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            placeholder="600036"
            className="input w-full"
          />
        </div>

        {/* Side */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSide('buy')}
            className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
              side === 'buy'
                ? 'bg-red-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            买入
          </button>
          <button
            type="button"
            onClick={() => setSide('sell')}
            className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
              side === 'sell'
                ? 'bg-green-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            卖出
          </button>
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">总数量（股）</label>
          <input
            type="number"
            value={qty}
            onChange={e => setQty(e.target.value)}
            min="100"
            step="100"
            className="input w-full"
          />
        </div>

        {/* Order Type */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">订单类型</label>
          <div className="grid grid-cols-4 gap-2">
            {(['market', 'limit', 'twap', 'vwap'] as OrderType[]).map(type => (
              <button
                key={type}
                type="button"
                onClick={() => setOrderType(type)}
                className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                  orderType === type
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {type === 'market' ? '市价' : type === 'limit' ? '限价' : type.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Limit Price */}
        {orderType === 'limit' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">限价</label>
            <input
              type="number"
              value={limitPrice}
              onChange={e => setLimitPrice(e.target.value)}
              step="0.01"
              placeholder="0.00"
              className="input w-full"
            />
          </div>
        )}

        {/* TWAP/VWAP shared: Start / End time */}
        {isAlgoType && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">开始时间</label>
              <input
                type="datetime-local"
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">结束时间</label>
              <input
                type="datetime-local"
                value={endTime}
                onChange={e => setEndTime(e.target.value)}
                className="input w-full"
              />
            </div>
          </div>
        )}

        {/* TWAP: Number of slices */}
        {orderType === 'twap' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">分片数量</label>
            <input
              type="number"
              value={numSlices}
              onChange={e => setNumSlices(e.target.value)}
              min="2"
              max="100"
              className="input w-full"
            />
          </div>
        )}

        {/* VWAP: Lookback days */}
        {orderType === 'vwap' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">回溯天数</label>
            <input
              type="number"
              value={lookbackDays}
              onChange={e => setLookbackDays(e.target.value)}
              min="1"
              max="30"
              className="input w-full"
            />
            <p className="text-xs text-gray-400 mt-1">
              用于计算历史成交量分布，决定每个时段的下单量
            </p>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={orderMutation.isPending || !symbol}
          className={`w-full py-3 rounded-lg font-medium transition-colors ${
            side === 'buy'
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-green-500 hover:bg-green-600 text-white'
          } disabled:opacity-50`}
        >
          {orderMutation.isPending
            ? '提交中...'
            : side === 'buy'
              ? '买入'
              : '卖出'}
        </button>

        {/* Error */}
        {orderMutation.isError && (
          <div className="text-red-500 text-sm mt-2">
            {orderMutation.error?.message || '下单失败'}
          </div>
        )}

        {/* Success */}
        {orderMutation.isSuccess && (
          <div className="text-green-600 text-sm mt-2">
            算法订单已提交: {orderMutation.data.order_id}
          </div>
        )}
      </form>
    </div>
  )
}
