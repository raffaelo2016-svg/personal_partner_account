import { formatDistanceToNow, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';

const DEFAULT_TZ = 'Europe/Moscow';

// Backend сериализует naive UTC-datetime без TZ-суффикса
// ("2026-04-21T18:56:06"). JS трактует такую строку как локальное
// время браузера, поэтому последующий toLocaleString(timeZone: ...)
// даёт сдвиг на (local − UTC). Принудительно дочитываем такую строку
// как UTC, добавляя 'Z', если TZ-маркера нет.
function parseIso(isoString: string): Date {
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(isoString);
  return new Date(hasTz ? isoString : isoString + 'Z');
}

export function formatDate(isoString: string, tz: string = DEFAULT_TZ): string {
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

export function formatDateShort(isoString: string, tz: string = DEFAULT_TZ): string {
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

export function formatDateTime(isoString: string, tz: string = DEFAULT_TZ): string {
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

export function formatTime(isoString: string, tz: string = DEFAULT_TZ): string {
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
