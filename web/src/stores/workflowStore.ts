import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type WorkflowType = 'factor-to-backtest' | 'ml-pipeline' | 'optimize';

export interface WorkflowStep {
  id: string;
  name: string;
  path: string;
  status: 'pending' | 'active' | 'completed' | 'skipped';
}

interface WorkflowContext {
  selectedFactors?: string[];
  factorICResults?: Record<string, number>;
  strategyId?: string;
  strategyConfig?: Record<string, any>;
  backtestId?: string;
  backtestResults?: any;
  modelId?: string;
  modelVersion?: string;
  experimentId?: string;
  optimizeConfig?: Record<string, any>;
  optimizeResults?: any;
}

interface WorkflowHistoryEntry {
  step: string;
  timestamp: number;
  context: Record<string, any>;
}

interface WorkflowState {
  currentWorkflow: WorkflowType | null;
  currentStep: string | null;
  steps: WorkflowStep[];
  context: WorkflowContext;
  history: WorkflowHistoryEntry[];
  startWorkflow: (type: WorkflowType) => void;
  nextStep: (context?: Record<string, any>) => void;
  prevStep: () => void;
  goToStep: (stepId: string) => void;
  updateContext: (context: Record<string, any>) => void;
  reset: () => void;
}

const WORKFLOW_STEPS: Record<WorkflowType, WorkflowStep[]> = {
  'factor-to-backtest': [
    { id: 'factors', name: '因子选择', path: '/factors', status: 'pending' },
    { id: 'strategy', name: '策略构建', path: '/strategies', status: 'pending' },
    { id: 'backtest', name: '回测验证', path: '/backtests', status: 'pending' },
    { id: 'analysis', name: '结果分析', path: '/backtests', status: 'pending' },
  ],
  'ml-pipeline': [
    { id: 'data', name: '数据准备', path: '/datasets', status: 'pending' },
    { id: 'features', name: '特征选择', path: '/factors', status: 'pending' },
    { id: 'training', name: '模型训练', path: '/ml', status: 'pending' },
    { id: 'backtest', name: '回测验证', path: '/backtests', status: 'pending' },
  ],
  'optimize': [
    { id: 'backtest', name: '回测结果', path: '/backtests', status: 'pending' },
    { id: 'constraints', name: '约束配置', path: '/optimize', status: 'pending' },
    { id: 'optimize', name: '组合优化', path: '/optimize', status: 'pending' },
    { id: 'risk', name: '风控检查', path: '/risk', status: 'pending' },
  ],
};

export const useWorkflowStore = create<WorkflowState>()(
  persist(
    (set, get) => ({
      currentWorkflow: null,
      currentStep: null,
      steps: [],
      context: {},
      history: [],
      startWorkflow: (type) => {
        const steps = WORKFLOW_STEPS[type].map((s, i) => ({
          ...s,
          status: i === 0 ? 'active' as const : 'pending' as const,
        }));
        set({ currentWorkflow: type, currentStep: steps[0].id, steps, context: {}, history: [] });
      },
      nextStep: (newContext) => {
        const { steps, currentStep, context, history } = get();
        const currentIndex = steps.findIndex(s => s.id === currentStep);
        if (currentIndex === -1 || currentIndex >= steps.length - 1) return;
        const updatedSteps = steps.map((s, i) => {
          if (i === currentIndex) return { ...s, status: 'completed' as const };
          if (i === currentIndex + 1) return { ...s, status: 'active' as const };
          return s;
        });
        set({
          steps: updatedSteps,
          currentStep: updatedSteps[currentIndex + 1].id,
          context: { ...context, ...newContext },
          history: [...history, { step: currentStep!, timestamp: Date.now(), context: newContext || {} }],
        });
      },
      prevStep: () => {
        const { steps, currentStep } = get();
        const currentIndex = steps.findIndex(s => s.id === currentStep);
        if (currentIndex <= 0) return;
        const updatedSteps = steps.map((s, i) => {
          if (i === currentIndex) return { ...s, status: 'pending' as const };
          if (i === currentIndex - 1) return { ...s, status: 'active' as const };
          return s;
        });
        set({ steps: updatedSteps, currentStep: updatedSteps[currentIndex - 1].id });
      },
      goToStep: (stepId) => {
        const { steps } = get();
        const targetIndex = steps.findIndex(s => s.id === stepId);
        if (targetIndex === -1) return;
        const updatedSteps = steps.map((s, i) => {
          if (i === targetIndex) return { ...s, status: 'active' as const };
          if (i < targetIndex) return { ...s, status: 'completed' as const };
          return { ...s, status: 'pending' as const };
        });
        set({ steps: updatedSteps, currentStep: stepId });
      },
      updateContext: (newContext) => {
        set((state) => ({ context: { ...state.context, ...newContext } }));
      },
      reset: () => {
        set({ currentWorkflow: null, currentStep: null, steps: [], context: {}, history: [] });
      },
    }),
    { name: 'cquant-workflow' }
  )
);
