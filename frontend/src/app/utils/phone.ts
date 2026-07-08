/**
 * Телефон: ввод с форматированием (+7 (XXX) XXX-XX-XX для РФ), E.164 для API.
 */

/** С запасом под скобки, пробелы и тире */
export const PHONE_INPUT_MAX = 32;

/** Единая подсказка под полем телефона */
export const PHONE_HINT_RU =
  'Россия: номер с 9… оформляется как +7 (9…); можно 8… или +7…; другие страны — с + и кодом (до 15 цифр).';

export function sanitizePhoneInput(raw: string): string {
  let s = raw.replace(/[^\d+\s()-]/g, '');
  const plusIdx = s.indexOf('+');
  if (plusIdx > 0) {
    s = s.replace(/\+/g, '');
    s = '+' + s;
  }
  return s.slice(0, PHONE_INPUT_MAX);
}

/** +7 (XXX) XXX-XX-XX — только цифры, начинается с 7, длина национальной части ≤10 */
function formatRu7Digits(d: string): string {
  if (!d.startsWith('7')) return '';
  const r = d.slice(1, 11);
  if (r.length === 0) return '+7';

  const g1 = r.slice(0, 3);
  const g2 = r.slice(3, 6);
  const g3 = r.slice(6, 8);
  const g4 = r.slice(8, 10);

  if (r.length <= 3) {
    return r.length === 3 ? `+7 (${g1})` : `+7 (${g1}`;
  }
  let out = `+7 (${g1})`;
  if (r.length <= 6) {
    return `${out} ${g2}`;
  }
  out += ` ${g2}`;
  if (r.length <= 8) {
    return `${out}-${g3}`;
  }
  out += `-${g3}`;
  if (r.length <= 10) {
    return `${out}-${g4}`;
  }
  return out;
}

/** Международный: + и группы по 3 цифры (без претензии на идеальный код страны) */
function formatInternationalDigits(d: string): string {
  if (!d.length) return '';
  if (d.startsWith('7') && d.length <= 11) {
    return formatRu7Digits(d);
  }
  const parts: string[] = [];
  let rest = d.slice(0, 15);
  while (rest.length > 3) {
    parts.push(rest.slice(0, 3));
    rest = rest.slice(3);
  }
  if (rest) parts.push(rest);
  return `+${parts.join(' ')}`;
}

/**
 * Нормализация цифр + красивое отображение при вводе.
 * РФ: 9… / 8… / 10 цифр / 7…; с «+» — международный формат.
 */
export function processPhoneInputForDisplay(raw: string): string {
  const s = sanitizePhoneInput(raw);
  const t = s.trim();
  if (!t) return '';

  if (t.startsWith('+')) {
    const rest = t.replace(/\D/g, '').slice(0, 15);
    if (!rest.length) return '+';
    if (rest.startsWith('7') && rest.length <= 11) {
      return formatRu7Digits(rest);
    }
    return formatInternationalDigits(rest);
  }

  let d = t.replace(/\D/g, '');
  if (!d) return '';

  if (d.startsWith('8')) {
    d = `7${d.slice(1, 11)}`;
  } else if (d.startsWith('7')) {
    d = d.slice(0, 11);
  } else {
    d = `7${d.slice(0, 10)}`;
  }

  if (d.startsWith('7') && d.length <= 11) {
    return formatRu7Digits(d);
  }

  return formatInternationalDigits(d.slice(0, 15));
}

/** @deprecated используйте processPhoneInputForDisplay */
export function sanitizePhoneInputRu(raw: string): string {
  return processPhoneInputForDisplay(raw);
}

/** Нормализация: РФ — 10 цифр → +7…; 8XXXXXXXXXX → +7…; иначе международный + и 8–15 цифр */
export function normalizePhoneToE164(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  let d = trimmed.replace(/\D/g, '');
  if (d.length < 10) return null;

  if (trimmed.startsWith('+')) {
    const rest = d;
    if (rest.length >= 10 && rest.length <= 15) return `+${rest}`;
    return null;
  }

  if (d.length === 10) d = `7${d}`;
  else if (d.length === 11 && d.startsWith('8')) d = `7${d.slice(1)}`;

  if (d.length < 10 || d.length > 15) return null;
  return `+${d}`;
}

/** Обязательное поле */
export function validatePhoneField(phone: string): string | null {
  const trimmed = phone.trim();
  if (!trimmed) return 'Укажите номер телефона';
  if (!normalizePhoneToE164(trimmed)) {
    const digits = trimmed.replace(/\D/g, '').length;
    if (digits < 10) return 'Введите не меньше 10 цифр номера';
    return 'Неверная длина или формат (с кодом страны — до 15 цифр)';
  }
  return null;
}

/** Необязательное поле: пусто — ок, иначе как validatePhoneField */
export function validatePhoneFieldOptional(phone: string): string | null {
  if (!phone.trim()) return null;
  return validatePhoneField(phone);
}

/** Для API: пустая строка → null, иначе E.164 или null при ошибке */
export function normalizePhoneForApi(raw: string): string | null {
  const t = raw.trim();
  if (!t) return null;
  return normalizePhoneToE164(t);
}

/** Для blur: показывать ошибку только если поле не пустое (необязательное) */
export function phoneErrorAfterBlur(raw: string, required: boolean): string | null {
  if (required) return validatePhoneField(raw);
  const t = raw.trim();
  if (!t) return null;
  return validatePhoneField(raw);
}
