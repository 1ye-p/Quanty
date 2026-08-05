import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { riskApi } from '@/lib/api/risk';
import type { RiskEvent } from '@/lib/api/risk';
import { extendedQueryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';

const severityColors: Record<RiskEvent['severity'], string> = {
  low: 'bg-blue-100 text-blue-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

export const RiskEventHistory: React.FC = () => {
  const { t } = useTranslation();
  const { data: events, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.risk.events(),
    queryFn: () => riskApi.getEvents(),
  });

  if (isLoading) return <div className="text-center py-4 text-gray-500">{t('common.loading')}</div>;
  if (error) return <div className="text-center py-8 text-red-500">{t('component.risk.event_history.load_failed', { message: error.message })}</div>;
  if (!events?.length) {
    return <div className="text-center py-8 text-gray-400">{t('component.risk.event_history.empty')}</div>;
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium text-gray-800 mb-4">{t('component.risk.event_history.title')}</h3>
      <div className="space-y-3">
        {events.map(event => (
          <div key={event.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
            <span className={cn("text-xs px-2 py-0.5 rounded", severityColors[event.severity])}>
              {event.severity}
            </span>
            <div className="flex-1">
              <div className="font-medium text-gray-800">{event.title}</div>
              <div className="text-sm text-gray-500">{event.description}</div>
              <div className="text-xs text-gray-400 mt-1">
                {new Date(event.created_at).toLocaleString('zh-CN')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
