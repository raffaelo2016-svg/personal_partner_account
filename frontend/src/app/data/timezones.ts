export interface TimezoneMeta {
  short: string;
  offset: string;
}

export const TIMEZONE_META: Record<string, TimezoneMeta> = {
  'Europe/Kaliningrad': { short: 'КАЛ', offset: 'UTC+2' },
  'Europe/Moscow': { short: 'МСК', offset: 'UTC+3' },
  'Europe/Samara': { short: 'САМ', offset: 'UTC+4' },
  'Asia/Yekaterinburg': { short: 'ЕКБ', offset: 'UTC+5' },
  'Asia/Omsk': { short: 'ОМСК', offset: 'UTC+6' },
  'Asia/Novosibirsk': { short: 'НСК', offset: 'UTC+7' },
  'Asia/Irkutsk': { short: 'ИРК', offset: 'UTC+8' },
  'Asia/Yakutsk': { short: 'ЯКТ', offset: 'UTC+9' },
  'Asia/Vladivostok': { short: 'ВЛД', offset: 'UTC+10' },
  'Asia/Magadan': { short: 'МГД', offset: 'UTC+11' },
  'Asia/Kamchatka': { short: 'ПКТ', offset: 'UTC+12' },
};

export const DEFAULT_TIMEZONE = 'Europe/Moscow';

export function getTimezoneMeta(timezone?: string | null): TimezoneMeta {
  return TIMEZONE_META[timezone ?? DEFAULT_TIMEZONE] ?? TIMEZONE_META[DEFAULT_TIMEZONE];
}

export function formatTimeInTimezone(timezone: string | null | undefined, date = new Date()): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: timezone || DEFAULT_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
