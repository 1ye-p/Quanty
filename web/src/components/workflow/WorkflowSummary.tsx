import { useNavigate } from 'react-router-dom'
import { useWorkflowStore } from '@/stores/workflowStore'

interface WorkflowSummaryProps {
  onClose: () => void
}

export function WorkflowSummary({ onClose }: WorkflowSummaryProps) {
  const navigate = useNavigate()
  const { context, history, reset } = useWorkflowStore()

  const handleNewWorkflow = () => {
    reset()
    onClose()
    navigate('/')
  }

  const handleGoHome = () => {
    onClose()
    navigate('/')
  }

  // Gather summary data from workflow context
  const factorCount = context.selectedFactors?.length ?? 0
  const hasICResults = context.factorICResults && Object.keys(context.factorICResults).length > 0
  const hasBacktest = !!context.backtestId
  const hasModel = !!context.modelId
  const hasOptimize = !!context.optimizeResults
  const stepsCompleted = history.length

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-5 border-b">
          <h2 className="text-lg font-semibold text-gray-900">工作流完成</h2>
          <p className="text-sm text-gray-500 mt-1">所有步骤已完成，以下是工作流摘要</p>
        </div>

        <div className="p-5 space-y-4">
          {/* Steps summary */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">
              {stepsCompleted}
            </span>
            <span>个步骤已完成</span>
          </div>

          {/* Results summary */}
          <div className="space-y-3">
            {factorCount > 0 && (
              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <span className="text-sm text-gray-700">选择因子</span>
                <span className="font-semibold text-blue-700">{factorCount} 个</span>
              </div>
            )}

            {hasICResults && (
              <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                <span className="text-sm text-gray-700">IC 计算</span>
                <span className="font-semibold text-purple-700">已完成</span>
              </div>
            )}

            {hasBacktest && (
              <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                <span className="text-sm text-gray-700">回测</span>
                <div className="text-right">
                  <span className="font-mono text-xs text-gray-500 block">{context.backtestId?.slice(0, 12)}...</span>
                  {context.backtestResults?.sharpe_ratio != null && (
                    <span className="text-sm font-semibold text-green-700">
                      Sharpe: {Number(context.backtestResults.sharpe_ratio).toFixed(3)}
                    </span>
                  )}
                </div>
              </div>
            )}

            {hasModel && (
              <div className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                <span className="text-sm text-gray-700">ML 模型</span>
                <span className="font-mono text-xs text-orange-700">{context.modelId?.slice(0, 12)}...</span>
              </div>
            )}

            {hasOptimize && (
              <div className="flex items-center justify-between p-3 bg-indigo-50 rounded-lg">
                <span className="text-sm text-gray-700">组合优化</span>
                <span className="font-semibold text-indigo-700">已完成</span>
              </div>
            )}

            {factorCount === 0 && !hasBacktest && !hasModel && !hasOptimize && (
              <div className="text-center text-gray-400 py-4 text-sm">
                暂无工作流结果数据
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 p-5 border-t">
          <button onClick={handleGoHome} className="btn-secondary">
            返回首页
          </button>
          <button onClick={handleNewWorkflow} className="btn-primary">
            开始新工作流
          </button>
        </div>
      </div>
    </div>
  )
}
