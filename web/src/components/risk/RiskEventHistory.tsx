import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { riskApi } from '@/lib/api/risk';
import { cn } from '@/lib/utils';

export const RiskEventHistory: React.FC = () => {
  const { data: events, isLoading } = useQuery({
    queryKey: ['risk-events'],
    queryFn: () => riskApi.getEvents(),
  });

  if (isLoading) return <div className="text-center py-4 text-gray-500">加载中...</div>;
  if (!events?.length) {
    return <div className="text-center py-8 text-gray-400">暂无风控事件</div>;
  }

  const severityColors: Record<string, string> = {
    low: 'bg-blue-100 text-blue-700',
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium text-gray-800 mb-4">风控事件历史</h3>
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
