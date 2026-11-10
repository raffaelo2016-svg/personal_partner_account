export interface TaskDeadline {
  due_date?: string | null;
  due_at?: string | null;
  status?: string;
}

const MOSCOW_TIME_ZONE = 'Europe/Moscow';

export function taskDeadlineTimestamp(task: TaskDeadline): number | null {
  const value = task.due_at
    ?? (task.due_date ? `${task.due_date}T23:59:59.999+03:00` : null);
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function isTaskOverdue(task: TaskDeadline, now = Date.now()): boolean {
  const deadline = taskDeadlineTimestamp(task);
  return task.status !== 'completed' && deadline !== null && deadline < now;
}

// Old stored overdue statuses can remain after a deadline was moved or removed.
export function taskDisplayStatus(task: TaskDeadline, now = Date.now()): string {
  if (task.status === 'completed') return 'completed';
  if (isTaskOverdue(task, now)) return 'overdue';
  return task.status === 'overdue' ? 'pending' : (task.status ?? 'pending');
}

export function formatTaskDeadline(task: TaskDeadline): string {
  const timestamp = taskDeadlineTimestamp(task);
  if (timestamp === null) return 'Без срока';
  const date = new Intl.DateTimeFormat('ru-RU', {
    timeZone: MOSCOW_TIME_ZONE,
    day: '2-digit', month: '2-digit', year: 'numeric',
    ...(task.due_at ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' as const } : {}),
  }).format(timestamp);
  return task.due_at ? `${date} МСК` : `${date}, до конца дня (МСК)`;
}

export function taskDeadlineFields(task: TaskDeadline): { due_date: string; due_time: string } {
  if (!task.due_at) return { due_date: task.due_date ?? '', due_time: '' };
  const timestamp = taskDeadlineTimestamp(task);
  if (timestamp === null) return { due_date: '', due_time: '' };
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: MOSCOW_TIME_ZONE,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(timestamp);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? '';
  return {
    due_date: `${part('year')}-${part('month')}-${part('day')}`,
    due_time: `${part('hour')}:${part('minute')}`,
  };
}

export function taskDeadlinePayload(date: string, time: string): { due_date: string | null; due_at: string | null } {
  return {
    due_date: date || null,
    // The field is a Moscow wall-clock time, regardless of the browser zone.
    due_at: date && time ? new Date(`${date}T${time}:00+03:00`).toISOString() : null,
  };
}
