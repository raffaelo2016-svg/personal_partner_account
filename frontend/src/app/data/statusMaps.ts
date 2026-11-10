export const STATUS_LABELS: Record<string, string> = {
  documents_collection: 'Сбор документов',
  documents_formation: 'Формирование документов',
  sent_to_court: 'Отправка в суд',
  documents_decision: 'Документы приняты / не приняты',
  waiting_hearing: 'Ожидание заседания',
  restructuring: 'Реструктуризация',
  auction: 'Торги',
  realization: 'Реализация',
  completed: 'Завершено',
};

export const STATUS_BADGE_COLORS: Record<string, string> = {
  documents_collection: 'bg-blue-100 text-blue-700',
  documents_formation: 'bg-indigo-100 text-indigo-700',
  sent_to_court: 'bg-orange-100 text-orange-700',
  documents_decision: 'bg-emerald-100 text-emerald-700',
  waiting_hearing: 'bg-cyan-100 text-cyan-700',
  restructuring: 'bg-purple-100 text-purple-700',
  auction: 'bg-amber-100 text-amber-700',
  realization: 'bg-green-100 text-green-700',
  completed: 'bg-teal-100 text-teal-700',
};

export const STATUS_DOT_COLORS: Record<string, string> = {
  documents_collection: 'bg-blue-500',
  documents_formation: 'bg-indigo-500',
  sent_to_court: 'bg-orange-500',
  documents_decision: 'bg-emerald-500',
  waiting_hearing: 'bg-cyan-500',
  restructuring: 'bg-purple-500',
  auction: 'bg-amber-500',
  realization: 'bg-green-500',
  completed: 'bg-teal-500',
};

export const PARTNER_STATUS_LABELS: Record<string, string> = {
  pending: 'На проверке',
  active: 'Активный',
  blocked: 'Заблокирован',
};

export const PARTNER_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  active: 'bg-green-100 text-green-700 border-green-200',
  blocked: 'bg-red-100 text-red-700 border-red-200',
};

export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

export function getStatusBadgeColor(status: string): string {
  return STATUS_BADGE_COLORS[status] || 'bg-gray-100 text-gray-700';
}

export function getStatusDotColor(status: string): string {
  return STATUS_DOT_COLORS[status] || 'bg-gray-500';
}
