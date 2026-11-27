import { REGION_TIMEZONES } from '@/app/data/regionTimezones';
import { MOSCOW_TIME_ZONE } from './formatDate';

/** Пояс партнёра по его региону; без региона — Москва. */
export function timezoneForRegion(region?: string | null): string {
  const key = region?.trim();
  if (!key) return MOSCOW_TIME_ZONE;
  return REGION_TIMEZONES[key] ?? MOSCOW_TIME_ZONE;
}

/** Время «сейчас» у партнёра в формате ЧЧ:ММ. */
export function formatPartnerTime(date: Date, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone,
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: MOSCOW_TIME_ZONE,
    }).format(date);
  }
}

/**
 * Смещение пояса на указанный момент: «UTC+3», «UTC+7», «UTC-7».
 * Считается по стенной дате пояса, поэтому учитывает перевод часов.
 */
export function utcOffsetLabel(date: Date, timeZone: string): string {
  let offsetMinutes: number;
  try {
    offsetMinutes = zoneOffsetMinutes(date, timeZone);
  } catch {
    offsetMinutes = zoneOffsetMinutes(date, MOSCOW_TIME_ZONE);
  }
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const abs = Math.abs(offsetMinutes);
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  return minutes === 0 ? `UTC${sign}${hours}` : `UTC${sign}${hours}:${String(minutes).padStart(2, '0')}`;
}

function zoneOffsetMinutes(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(date);
  const values: Record<string, string> = {};
  for (const part of parts) {
    if (part.type !== 'literal') values[part.type] = part.value;
  }
  const wallClock = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );
  return Math.round((wallClock - date.getTime()) / 60_000);
}
