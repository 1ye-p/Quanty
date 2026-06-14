/**
 * Model catalog display grouped by category.
 * Shows available ML model types with descriptions.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { mlApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface ModelInfo {
  name: string
  display_name: string
  engine: string
  description: string
  category_label?: string
}

export function ModelsTab() {
  const { data: modelsCatalog, isLoading } = useQuery({
    queryKey: extendedQueryKeys.ml.modelsCatalog(),
    queryFn: () => mlApi.modelsCatalog(),
    staleTime: 300_000,
  })

  const groupedModels = useMemo(() => {
    if (!modelsCatalog) return []
    const groups: Record<string, ModelInfo[]> = {}
    const order = ['Traditional', 'Deep Learning', 'Ensemble', 'Linear', 'Online', 'Specialized']
    for (const info of Object.values(modelsCatalog) as ModelInfo[]) {
      const label = info.category_label || 'Other'
      if (!groups[label]) groups[label] = []
      groups[label].push(info)
    }
    return order
      .filter(label => groups[label])
      .map(label => ({ label, models: groups[label] }))
      .concat(
        Object.entries(groups)
          .filter(([label]) => !order.includes(label))
          .map(([label, models]) => ({ label, models }))
      )
  }, [modelsCatalog])

  if (isLoading) return <p className="text-gray-400">Loading model catalog...</p>

  return (
    <div className="space-y-4">
      {groupedModels.map(group => (
        <div key={group.label} className="card">
          <h3 className="font-semibold text-gray-800 mb-3">{group.label}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {group.models.map(m => (
              <div key={m.name} className="p-3 bg-gray-50 rounded-lg">
                <div className="font-medium text-gray-900 text-sm">{m.display_name}</div>
                <div className="text-xs text-gray-500 mt-1">{m.description}</div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px]">{m.name}</span>
                  {m.engine === 'qlib' && (
                    <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded text-[10px]">qlib</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
