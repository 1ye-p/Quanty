import { useParams } from 'react-router-dom'
import { FeatureImportanceTab } from '@/components/FeatureImportanceTab'

export function BacktestFeatureImportanceTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  if (!selectedId) return null

  return <FeatureImportanceTab modelVersion={selectedId} />
}
