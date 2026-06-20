import { describe, expect, it } from 'vitest';
import {
  sanitizeInnDigits,
  sanitizeKppDigits,
  validateInnForPartnerType,
  validateKpp,
} from './innKpp';

describe('sanitizeInnDigits', () => {
  it('пустая строка → пустая', () => {
    expect(sanitizeInnDigits('', 10)).toBe('');
  });

  it('убирает буквы, пробелы и спецсимволы', () => {
    expect(sanitizeInnDigits('12 ab-34.5', 10)).toBe('12345');
  });

  it('обрезает до maxLen=10', () => {
    expect(sanitizeInnDigits('12345678901234', 10)).toBe('1234567890');
  });

  it('обрезает до maxLen=12', () => {
    expect(sanitizeInnDigits('12345678901234', 12)).toBe('123456789012');
  });

  it('сохраняет строку короче maxLen', () => {
    expect(sanitizeInnDigits('1234', 10)).toBe('1234');
  });
});

describe('sanitizeKppDigits', () => {
  it('пустая строка → пустая', () => {
    expect(sanitizeKppDigits('')).toBe('');
  });

  it('убирает нецифровые символы', () => {
    expect(sanitizeKppDigits('77a01b01c001')).toBe('770101001');
  });

  it('обрезает до 9 цифр', () => {
    expect(sanitizeKppDigits('770012345678')).toBe('770012345');
  });
});

describe('validateInnForPartnerType — legal', () => {
  it('10 цифр → null', () => {
    expect(validateInnForPartnerType('1234567890', 'legal')).toBeNull();
  });

  it('9 цифр → ошибка', () => {
    expect(validateInnForPartnerType('123456789', 'legal')).toBe('ИНН организации — ровно 10 цифр');
  });

  it('12 цифр → ошибка (legal ждёт 10)', () => {
    expect(validateInnForPartnerType('123456789012', 'legal')).toBe('ИНН организации — ровно 10 цифр');
  });

  it('пусто → ошибка', () => {
    expect(validateInnForPartnerType('', 'legal')).toBe('ИНН организации — ровно 10 цифр');
  });

  it('игнорирует нецифровые при подсчёте длины', () => {
    expect(validateInnForPartnerType('12 34 56 78 90', 'legal')).toBeNull();
    expect(validateInnForPartnerType('abc1234567890', 'legal')).toBeNull();
  });
});

describe('validateInnForPartnerType — entrepreneur', () => {
  it('12 цифр → null', () => {
    expect(validateInnForPartnerType('123456789012', 'entrepreneur')).toBeNull();
  });

  it('10 цифр → ошибка', () => {
    expect(validateInnForPartnerType('1234567890', 'entrepreneur')).toBe('ИНН ИП — ровно 12 цифр');
  });

  it('пусто → ошибка', () => {
    expect(validateInnForPartnerType('', 'entrepreneur')).toBe('ИНН ИП — ровно 12 цифр');
  });
});

describe('validateKpp', () => {
  it('ровно 9 цифр с кодом причины 01 → null', () => {
    expect(validateKpp('770101001')).toBeNull();
  });

  it('ровно 9 цифр с кодом причины 99 → null', () => {
    expect(validateKpp('770199001')).toBeNull();
  });

  it('ровно 9 цифр с кодом причины 56 → null', () => {
    expect(validateKpp('123456789')).toBeNull();
  });

  it('8 цифр → ошибка длины', () => {
    expect(validateKpp('12345678')).toBe('КПП — ровно 9 цифр');
  });

  it('10 цифр → ошибка длины', () => {
    expect(validateKpp('1234567890')).toBe('КПП — ровно 9 цифр');
  });

  it('пусто → ошибка длины', () => {
    expect(validateKpp('')).toBe('КПП — ровно 9 цифр');
  });

  it('код причины 00 → ошибка', () => {
    expect(validateKpp('770100001')).toBe('Проверьте КПП (код причины постановки на учёт)');
  });

  it('игнорирует нецифровые', () => {
    expect(validateKpp('7701-01 001')).toBeNull();
  });
});
