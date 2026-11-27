/** Человеческие подписи статусов задачи. */
export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  in_progress: 'В работе',
  review: 'На проверке',
  completed: 'Выполнено',
  rejected: 'Отклонено',
  overdue: 'Просрочено',
};

export function taskStatusLabel(status: string | null | undefined): string {
  if (!status) return '';
  return TASK_STATUS_LABELS[status] ?? status;
}

/**
 * Выполненная и отклонённая задачи — финальные: срок по ним больше не
 * считается просроченным, даже если он уже прошёл.
 */
export function isFinalTaskStatus(status: string | null | undefined): boolean {
  return status === 'completed' || status === 'rejected';
}
