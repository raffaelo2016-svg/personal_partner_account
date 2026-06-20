/**
 * ИНН: только длина (10 — юрлица, 12 — ИП). Контрольные цифры ФНС не проверяются.
 * КПП: 9 цифр, позиции 5–6 — код причины постановки на учёт (01–99).
 */

export function sanitizeInnDigits(raw: string, maxLen: 10 | 12): string {
  return raw.replace(/\D/g, '').slice(0, maxLen);
}

export function sanitizeKppDigits(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 9);
}

/** Ошибка или null, если ок (только длина ИНН) */
export function validateInnForPartnerType(
  inn: string,
  partnerType: 'legal' | 'entrepreneur',
): string | null {
  const d = inn.replace(/\D/g, '');
  if (partnerType === 'legal') {
    if (d.length !== 10) return 'ИНН организации — ровно 10 цифр';
    return null;
  }
  if (d.length !== 12) return 'ИНН ИП — ровно 12 цифр';
  return null;
}

export function validateKpp(kpp: string): string | null {
  const d = kpp.replace(/\D/g, '');
  if (d.length !== 9) return 'КПП — ровно 9 цифр';
  const pp = parseInt(d.slice(4, 6), 10);
  if (pp < 1 || pp > 99) return 'Проверьте КПП (код причины постановки на учёт)';
  return null;
}
