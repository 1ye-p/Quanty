import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { detectExchange } from '@/lib/utils'

interface OrderFormProps {
  broker?: string
  onOrderPlaced?: () => void
}

export function OrderForm({ broker = 'paper', onOrderPlaced }: OrderFormProps) {
  const { t } = useTranslation()
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [qty, setQty] = useState('1000')
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market')
  const [limitPrice, setLimitPrice] = useState('')
  const queryClient = useQueryClient()

  const orderMutation = useMutation({
    mutationFn: tradingApi.placeOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.orders(broker) })
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.positions(broker) })
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.account(broker) })
      setSymbol('')
      setQty('1000')
      setLimitPrice('')
      onOrderPlaced?.()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!symbol || !qty) return

    const exchange = detectExchange(symbol)
    orderMutation.mutate({
      asset_id: `${exchange}:${symbol}`,
      side,
      qty: parseInt(qty),
      order_type: orderType,
      limit_price: limitPrice ? parseFloat(limitPrice) : undefined,
      broker,
    })
  }

  return (
    <div className="card">
      <h2 className="font-semibold text-gray-800 mb-4">{t('component.trading.order_form.title')}</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Symbol */}
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t('component.trading.order_form.symbol')}</label>
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
          <label className="block text-sm text-gray-600 mb-1">{t('component.trading.order_form.qty')}</label>
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
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setOrderType('market')}
            className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
              orderType === 'market'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t('component.trading.order_form.type_market')}
          </button>
          <button
            type="button"
            onClick={() => setOrderType('limit')}
            className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
              orderType === 'limit'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t('component.trading.order_form.type_limit')}
          </button>
        </div>

        {/* Limit Price (conditional) */}
        {orderType === 'limit' && (
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('component.trading.order_form.limit_price')}</label>
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
            ? t('component.trading.order_form.submitting')
            : side === 'buy'
              ? t('component.trading.shared.side_buy')
              : t('component.trading.shared.side_sell')}
        </button>

        {/* Error */}
        {orderMutation.isError && (
          <div className="text-red-500 text-sm mt-2">
            {orderMutation.error?.message || t('component.trading.order_form.place_failed')}
          </div>
        )}

        {/* Success */}
        {orderMutation.isSuccess && (
          <div className="text-green-600 text-sm mt-2">
            {t('component.trading.order_form.submitted', { order_id: orderMutation.data.order_id, status: orderMutation.data.status })}
          </div>
        )}
      </form>
    </div>
  )
}
