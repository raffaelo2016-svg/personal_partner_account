import { formatDateShort } from '@/app/utils/formatDate';

interface ChatDateSeparatorProps {
  createdAt: string;
  previousCreatedAt?: string;
  timezone: string;
}

export default function ChatDateSeparator({ createdAt, previousCreatedAt, timezone }: ChatDateSeparatorProps) {
  const date = formatDateShort(createdAt, timezone);
  if (date === '—' || (previousCreatedAt && date === formatDateShort(previousCreatedAt, timezone))) return null;

  return (
    <div className="mb-4 flex items-center gap-3 text-xs font-medium text-gray-500" role="separator" aria-label={date}>
      <span className="h-px flex-1 bg-gray-200" aria-hidden="true" />
      <span>{date}</span>
      <span className="h-px flex-1 bg-gray-200" aria-hidden="true" />
    </div>
  );
}
