/** Пороги подсветки партнёров без клиентского потока. */
export const PARTNER_PAUSE_LIST_DAYS = 14;
export const PARTNER_PAUSE_BLUE_AFTER_DAYS = 15;
export const PARTNER_PAUSE_RED_AFTER_DAYS = 30;

export type PartnerPauseTone = 'neutral' | 'blue' | 'red';

/**
 * Тон строки по числу дней без клиента:
 * больше 30 — красный, больше 15 — синий, иначе без подсветки.
 */
export function partnerPauseTone(days: number): PartnerPauseTone {
  if (days > PARTNER_PAUSE_RED_AFTER_DAYS) return 'red';
  if (days > PARTNER_PAUSE_BLUE_AFTER_DAYS) return 'blue';
  return 'neutral';
}

/** Склонение: 1 день, 2 дня, 5 дней. */
export function formatPauseDays(days: number): string {
  const abs = Math.abs(days);
  const lastTwo = abs % 100;
  const last = abs % 10;

  if (lastTwo >= 11 && lastTwo <= 14) return `${days} дней`;
  if (last === 1) return `${days} день`;
  if (last >= 2 && last <= 4) return `${days} дня`;
  return `${days} дней`;
}

export function partnerPauseHint(days: number): string {
  const tone = partnerPauseTone(days);
  if (tone === 'red') return `Без клиента ${formatPauseDays(days)} — критично`;
  if (tone === 'blue') return `Без клиента ${formatPauseDays(days)} — пора напомнить`;
  return `Без клиента ${formatPauseDays(days)}`;
}
