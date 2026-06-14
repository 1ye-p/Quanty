import { useParams } from 'react-router-dom'
import { useBacktestCompareStore } from '@/stores/backtestCompareStore'
import { ModelCompareTab } from '@/components/ModelCompareTab'

export function BacktestModelCompareTab() {
  const { id: selectedId } = useParams<{ id: string }>()
  const { selectedIds } = useBacktestCompareStore()

  if (!selectedId) return null

  return <ModelCompareTab backtestId={selectedId} selectedModels={selectedIds} />
}
