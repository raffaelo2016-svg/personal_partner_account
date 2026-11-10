// Ссылки на карточку дела в КАД Арбитр (kad.arbitr.ru).
//
// КАД умеет открывать дело по номеру без GUID:
//   https://kad.arbitr.ru/Kad/Card?number=А66-5146/2026
// Номер подставляется в query-параметр `number`, сайт сам находит карточку,
// поэтому хранить GUID дела в нашей базе не нужно.
const KAD_HOSTS = new Set(['kad.arbitr.ru', 'www.kad.arbitr.ru']);
const KAD_CARD_PATH = '/Kad/Card';

/** Ограничение поля `case_number` в API. */
export const CASE_NUMBER_MAX_LENGTH = 50;

/** Номер дела в том виде, в котором его понимает КАД: без пробелов, в верхнем регистре. */
export function normalizeCaseNumber(raw?: string | null): string {
  if (!raw) return '';
  return raw.replace(/\s+/g, '').toUpperCase();
}

/**
 * Проверяет номер дела перед сохранением.
 * Возвращает текст ошибки или null, если номер можно сохранять.
 * Пустое значение допустимо — так администратор удаляет номер.
 */
export function validateCaseNumber(raw?: string | null): string | null {
  const normalized = normalizeCaseNumber(raw);
  if (!normalized) return null;
  if (normalized.length > CASE_NUMBER_MAX_LENGTH) {
    return `Номер дела длиннее ${CASE_NUMBER_MAX_LENGTH} символов`;
  }
  if (!/\d/.test(normalized)) {
    return 'В номере дела должны быть цифры';
  }
  return null;
}

/**
 * Пустое значение или заглушка вместо номера: «—», «-», «–».
 * Такие значения нельзя считать заполненным номером дела.
 */
export function isBlankCaseNumber(raw?: string | null): boolean {
  const normalized = normalizeCaseNumber(raw);
  return !normalized || /^[-—–]+$/.test(normalized);
}

/**
 * Ссылка на карточку дела в КАД Арбитр по номеру.
 * Возвращает null, если номер пустой или это заглушка («—»).
 */
export function kadCaseUrl(caseNumber?: string | null): string | null {
  if (isBlankCaseNumber(caseNumber)) return null;
  const normalized = normalizeCaseNumber(caseNumber);
  return `https://kad.arbitr.ru${KAD_CARD_PATH}?number=${encodeURIComponent(normalized)}`;
}

/**
 * Ссылка на дело для карточки клиента: явная сохранённая ссылка (если это
 * действительно КАД) имеет приоритет, иначе строим её из номера дела.
 * Внешние/небезопасные URL не используются — только https на kad.arbitr.ru.
 */
export function resolveCaseUrl(
  caseNumber?: string | null,
  explicitUrl?: string | null,
): string | null {
  const trusted = trustedKadUrl(explicitUrl);
  if (trusted) return trusted;
  return kadCaseUrl(caseNumber);
}

function trustedKadUrl(raw?: string | null): string | null {
  if (!raw) return null;
  const value = raw.trim();
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    if (!KAD_HOSTS.has(url.hostname.toLowerCase())) return null;
    return url.toString();
  } catch {
    return null;
  }
}
