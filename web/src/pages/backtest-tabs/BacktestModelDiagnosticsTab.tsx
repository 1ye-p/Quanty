import { useParams } from 'react-router-dom'
import { ModelDiagnosticsTab } from '@/components/ModelDiagnosticsTab'

export function BacktestModelDiagnosticsTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  if (!selectedId) return null

  return <ModelDiagnosticsTab modelVersion={selectedId} />
}
