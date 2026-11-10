import { CheckCircle2, FileText, FileCog, Send, Gavel, Clock } from 'lucide-react';
import type { ComponentType } from 'react';

export const CLIENT_STATUSES = [
  'documents_collection',
  'documents_formation',
  'sent_to_court',
  'documents_decision',
  'waiting_hearing',
  'restructuring',
  'auction',
  'realization',
  'completed',
] as const;

export type ClientStatus = (typeof CLIENT_STATUSES)[number];

export const BEFORE_COURT_STATUSES: ClientStatus[] = [
  'documents_collection',
  'documents_formation',
  'sent_to_court',
  'documents_decision',
];

export const IN_COURT_STATUSES: ClientStatus[] = [
  'waiting_hearing',
  'restructuring',
  'auction',
];

export const COMPLETED_STATUSES: ClientStatus[] = ['realization', 'completed'];

export const STATUS_LABELS: Record<ClientStatus, string> = {
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

export const STATUS_BADGE_CLASSES: Record<ClientStatus, string> = {
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

export const STATUS_BADGE_BORDERED: Record<ClientStatus, string> = {
  documents_collection: 'bg-blue-100 text-blue-700 border-blue-200',
  documents_formation: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  sent_to_court: 'bg-orange-100 text-orange-700 border-orange-200',
  documents_decision: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  waiting_hearing: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  restructuring: 'bg-purple-100 text-purple-700 border-purple-200',
  auction: 'bg-amber-100 text-amber-700 border-amber-200',
  realization: 'bg-green-100 text-green-700 border-green-200',
  completed: 'bg-teal-100 text-teal-700 border-teal-200',
};

export const STATUS_DOT_CLASSES: Record<ClientStatus, string> = {
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

type Icon = ComponentType<{ className?: string }>;

export const STATUS_OPTIONS: {
  value: ClientStatus;
  label: string;
  icon: Icon;
  color: string;
}[] = [
  { value: 'documents_collection', label: STATUS_LABELS.documents_collection, icon: FileText, color: 'text-blue-600' },
  { value: 'documents_formation', label: STATUS_LABELS.documents_formation, icon: FileCog, color: 'text-indigo-600' },
  { value: 'sent_to_court', label: STATUS_LABELS.sent_to_court, icon: Send, color: 'text-orange-600' },
  { value: 'documents_decision', label: STATUS_LABELS.documents_decision, icon: Gavel, color: 'text-emerald-600' },
  { value: 'waiting_hearing', label: STATUS_LABELS.waiting_hearing, icon: Clock, color: 'text-cyan-600' },
  { value: 'restructuring', label: STATUS_LABELS.restructuring, icon: Clock, color: 'text-purple-600' },
  { value: 'auction', label: STATUS_LABELS.auction, icon: Gavel, color: 'text-amber-600' },
  { value: 'realization', label: STATUS_LABELS.realization, icon: FileText, color: 'text-green-600' },
  { value: 'completed', label: STATUS_LABELS.completed, icon: CheckCircle2, color: 'text-teal-600' },
];

export function isClientStatus(value: string): value is ClientStatus {
  return (CLIENT_STATUSES as readonly string[]).includes(value);
}

export function getStatusLabel(status: string): string {
  return isClientStatus(status) ? STATUS_LABELS[status] : status;
}

export function getStatusBadgeClass(status: string, bordered = false): string {
  if (isClientStatus(status)) {
    return bordered ? STATUS_BADGE_BORDERED[status] : STATUS_BADGE_CLASSES[status];
  }
  return bordered ? 'bg-gray-100 text-gray-700 border-gray-200' : 'bg-gray-100 text-gray-700';
}

export function getStatusDotClass(status: string): string {
  return isClientStatus(status) ? STATUS_DOT_CLASSES[status] : 'bg-gray-500';
}

export function getCategoryLabel(status: string): string {
  if (BEFORE_COURT_STATUSES.includes(status as ClientStatus)) return 'ДО подачи в суд';
  if (IN_COURT_STATUSES.includes(status as ClientStatus)) return 'УЖЕ в суде';
  if (COMPLETED_STATUSES.includes(status as ClientStatus)) return 'Завершено';
  return '—';
}
