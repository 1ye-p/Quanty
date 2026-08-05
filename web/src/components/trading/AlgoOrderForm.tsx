import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi, type AlgoOrderParams } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { detectExchange } from '@/lib/utils'

type OrderType = 'market' | 'limit' | 'twap' | 'vwap'

interface AlgoOrderFormProps {
  broker?: string
  onSubmitted?: () => void
}

export function AlgoOrderForm({ broker = 'paper', onSubmitted }: AlgoOrderFormProps) {
  const { t } = useTranslation()
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
      <h2 className="font-semibold text-gray-800 mb-4">{t('component.trading.algo_order_form.title')}</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Symbol */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.symbol')}</label>
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
            {t('component.trading.shared.side_buy')}
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
            {t('component.trading.shared.side_sell')}
          </button>
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.total_qty')}</label>
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
          <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.order_type')}</label>
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
                {type === 'market'
                  ? t('component.trading.algo_order_form.type_market')
                  : type === 'limit'
                    ? t('component.trading.algo_order_form.type_limit')
                    : type.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Limit Price */}
        {orderType === 'limit' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.limit_price')}</label>
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
              <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.start_time')}</label>
              <input
                type="datetime-local"
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.end_time')}</label>
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
            <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.num_slices')}</label>
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
            <label className="block text-sm text-gray-600 mb-1">{t('component.trading.algo_order_form.lookback_days')}</label>
            <input
              type="number"
              value={lookbackDays}
              onChange={e => setLookbackDays(e.target.value)}
              min="1"
              max="30"
              className="input w-full"
            />
            <p className="text-xs text-gray-400 mt-1">
              {t('component.trading.algo_order_form.lookback_hint')}
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
            ? t('component.trading.algo_order_form.submitting')
            : side === 'buy'
              ? t('component.trading.shared.side_buy')
              : t('component.trading.shared.side_sell')}
        </button>

        {/* Error */}
        {orderMutation.isError && (
          <div className="text-red-500 text-sm mt-2">
            {orderMutation.error?.message || t('component.trading.algo_order_form.place_failed')}
          </div>
        )}

        {/* Success */}
        {orderMutation.isSuccess && (
          <div className="text-green-600 text-sm mt-2">
            {t('component.trading.algo_order_form.submitted', { order_id: orderMutation.data.order_id })}
          </div>
        )}
      </form>
    </div>
  )
}
