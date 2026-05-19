interface Props { status: string }

const STATUS_CLASS: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  running:   'bg-blue-100 text-blue-800',
  failed:    'bg-red-100 text-red-800',
  pending:   'bg-yellow-100 text-yellow-800',
  ok:        'bg-green-100 text-green-800',
  duplicate: 'bg-gray-100 text-gray-600',
  error:     'bg-red-100 text-red-800',
}

export function StatusBadge({ status }: Props) {
  const cls = STATUS_CLASS[status.toLowerCase()] ?? 'bg-gray-100 text-gray-600'
  return <span className={`badge ${cls}`}>{status}</span>
}
