import { formatDistanceToNow, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';

export const MOSCOW_TIME_ZONE = 'Europe/Moscow';

// Backend сериализует naive UTC-datetime без TZ-суффикса
// ("2026-04-21T18:56:06"). JS трактует такую строку как локальное
// время браузера, поэтому последующий toLocaleString(timeZone: ...)
// даёт сдвиг на (local − UTC). Принудительно дочитываем такую строку
// как UTC, добавляя 'Z', если TZ-маркера нет.
function parseIso(isoString: string): Date {
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(isoString);
  return new Date(hasTz ? isoString : isoString + 'Z');
}

export function formatDate(isoString: string, tz: string = MOSCOW_TIME_ZONE): string {
  if (!isoString) return '—';
  const date = parseIso(isoString);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: tz,
  });
}

export function formatDateShort(isoString: string, tz: string = MOSCOW_TIME_ZONE): string {
  if (!isoString) return '—';
  const date = parseIso(isoString);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: tz,
  });
}

export function formatDateTime(isoString: string, tz: string = MOSCOW_TIME_ZONE): string {
  if (!isoString) return '—';
  const date = parseIso(isoString);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: tz,
  });
}

export function formatTime(isoString: string, tz: string = MOSCOW_TIME_ZONE): string {
  if (!isoString) return '—';
  const date = parseIso(isoString);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: tz,
  });
}

export function formatRelative(isoString: string): string {
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(isoString);
  return formatDistanceToNow(parseISO(hasTz ? isoString : isoString + 'Z'), {
    addSuffix: true,
    locale: ru,
  });
}

export interface CalendarDateParts {
  year: number;
  month: number;
  day: number;
}

export function getMoscowDateParts(value: Date = new Date()): CalendarDateParts {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: MOSCOW_TIME_ZONE,
  }).formatToParts(value);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value);
  return { year: get('year'), month: get('month'), day: get('day') };
}

export function todayInMoscow(value: Date = new Date()): string {
  const { year, month, day } = getMoscowDateParts(value);
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function dateOnlyDayNumber(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match.map(Number);
  const result = Date.UTC(year, month - 1, day) / 86_400_000;
  return Number.isFinite(result) ? result : null;
}

export function daysUntilMoscowDate(value: string, now: Date = new Date()): number {
  const target = dateOnlyDayNumber(value);
  const today = dateOnlyDayNumber(todayInMoscow(now));
  if (target === null || today === null) return 0;
  return target - today;
}

export function isBeforeMoscowToday(value: string, now: Date = new Date()): boolean {
  return daysUntilMoscowDate(value, now) < 0;
}
