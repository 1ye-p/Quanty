import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { WorkflowStep } from '../../stores/workflowStore';
import { WorkflowSummary } from './WorkflowSummary';

interface WorkflowBarProps {
  steps: WorkflowStep[];
  currentStep: string;
  onPrev: () => void;
  onNext: (context?: Record<string, any>) => void;
  onReset: () => void;
}

export function WorkflowBar({ steps, currentStep, onPrev, onNext, onReset }: WorkflowBarProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showSummary, setShowSummary] = useState(false);
  const currentIndex = steps.findIndex(s => s.id === currentStep);
  const allCompleted = steps.every(s => s.status === 'completed');

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200 px-4 py-2 shadow-sm">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          {steps.map((step, index) => (
            <React.Fragment key={step.id}>
              <button
                onClick={() => navigate(step.path)}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  step.status === 'active' ? 'bg-brand-500 text-white' :
                  step.status === 'completed' ? 'bg-brand-100 text-brand-700' :
                  'text-gray-400'
                }`}
              >
                {step.status === 'completed' && '✓ '}{step.name}
              </button>
              {index < steps.length - 1 && <span className="text-gray-400">→</span>}
            </React.Fragment>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onPrev} disabled={currentIndex === 0} className="btn-secondary disabled:opacity-50">{t('component.workflow.bar.prev_step')}</button>
          {allCompleted ? (
            <button onClick={() => setShowSummary(true)} className="btn-primary">{t('component.workflow.bar.view_summary')}</button>
          ) : (
            <button onClick={() => onNext()} disabled={currentIndex === steps.length - 1} className="btn-primary disabled:opacity-50">{t('component.workflow.bar.next_step')}</button>
          )}
          <button onClick={onReset} className="btn-secondary text-red-500">{t('component.workflow.bar.reset')}</button>
        </div>
      </div>
      {showSummary && <WorkflowSummary onClose={() => setShowSummary(false)} />}
    </div>
  );
}
