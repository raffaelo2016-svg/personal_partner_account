import { describe, expect, it } from 'vitest';
import {
  PHONE_INPUT_MAX,
  normalizePhoneForApi,
  normalizePhoneToE164,
  phoneErrorAfterBlur,
  processPhoneInputForDisplay,
  sanitizePhoneInput,
  sanitizePhoneInputRu,
  validatePhoneField,
  validatePhoneFieldOptional,
} from './phone';

describe('sanitizePhoneInput', () => {
  it('вырезает буквы', () => {
    expect(sanitizePhoneInput('abc')).toBe('');
    expect(sanitizePhoneInput('abc123+def456')).toBe('+123456');
  });

  it('сохраняет цифры, скобки, пробелы и тире', () => {
    expect(sanitizePhoneInput('(999) 123-45-67')).toBe('(999) 123-45-67');
  });

  it('перемещает + в начало, если он в середине', () => {
    expect(sanitizePhoneInput('1+2+3')).toBe('+123');
    expect(sanitizePhoneInput('79+12345')).toBe('+7912345');
  });

  it('сохраняет ведущий + без дубликатов', () => {
    expect(sanitizePhoneInput('+79991234567')).toBe('+79991234567');
  });

  it('обрезает длину до PHONE_INPUT_MAX', () => {
    const long = '+' + '1'.repeat(100);
    expect(sanitizePhoneInput(long).length).toBe(PHONE_INPUT_MAX);
  });
});

describe('processPhoneInputForDisplay', () => {
  it('пустая строка → пустая', () => {
    expect(processPhoneInputForDisplay('')).toBe('');
    expect(processPhoneInputForDisplay('   ')).toBe('');
  });

  it('одиночный + сохраняется', () => {
    expect(processPhoneInputForDisplay('+')).toBe('+');
  });

  it('одна цифра 9 → +7 (9', () => {
    expect(processPhoneInputForDisplay('9')).toBe('+7 (9');
  });

  it('три девятки → +7 (999)', () => {
    expect(processPhoneInputForDisplay('999')).toBe('+7 (999)');
  });

  it('10 цифр с ведущей 9 → полный RU формат', () => {
    expect(processPhoneInputForDisplay('9991234567')).toBe('+7 (999) 123-45-67');
  });

  it('начинается с 8 → переводит в +7', () => {
    expect(processPhoneInputForDisplay('89991234567')).toBe('+7 (999) 123-45-67');
  });

  it('сохраняет уже форматированный +7-номер', () => {
    expect(processPhoneInputForDisplay('+79991234567')).toBe('+7 (999) 123-45-67');
    expect(processPhoneInputForDisplay('+7 (999) 123-45-67')).toBe('+7 (999) 123-45-67');
  });

  it('международный номер с + группирует по 3 цифры', () => {
    expect(processPhoneInputForDisplay('+441234567890')).toBe('+441 234 567 890');
  });

  it('буквы игнорируются', () => {
    expect(processPhoneInputForDisplay('abc')).toBe('');
  });

  it('обрезает очень длинный международный номер до 15 цифр', () => {
    const out = processPhoneInputForDisplay('+79991234567999888');
    const digits = out.replace(/\D/g, '');
    expect(digits.length).toBe(15);
  });
});

describe('normalizePhoneToE164', () => {
  it('пустая строка → null', () => {
    expect(normalizePhoneToE164('')).toBeNull();
    expect(normalizePhoneToE164('   ')).toBeNull();
  });

  it('только буквы → null', () => {
    expect(normalizePhoneToE164('abc')).toBeNull();
  });

  it('меньше 10 цифр → null', () => {
    expect(normalizePhoneToE164('123456789')).toBeNull();
    expect(normalizePhoneToE164('+12345')).toBeNull();
  });

  it('10 цифр (RU без кода) → +7…', () => {
    expect(normalizePhoneToE164('9991234567')).toBe('+79991234567');
  });

  it('11 цифр с 8 → +7…', () => {
    expect(normalizePhoneToE164('89991234567')).toBe('+79991234567');
  });

  it('формат с пробелами и скобками нормализуется', () => {
    expect(normalizePhoneToE164('8 (999) 123-45-67')).toBe('+79991234567');
  });

  it('международный с + и 10–15 цифр проходит as-is', () => {
    expect(normalizePhoneToE164('+441234567890')).toBe('+441234567890');
    expect(normalizePhoneToE164('+1234567890')).toBe('+1234567890');
  });

  it('больше 15 цифр → null', () => {
    expect(normalizePhoneToE164('+1234567890123456')).toBeNull();
  });

  it('+7 в длинном варианте (15 цифр) остаётся валидным', () => {
    expect(normalizePhoneToE164('+799912345679998')).toBe('+799912345679998');
  });
});

describe('validatePhoneField (обязательное поле)', () => {
  it('пусто → "Укажите номер телефона"', () => {
    expect(validatePhoneField('')).toBe('Укажите номер телефона');
    expect(validatePhoneField('   ')).toBe('Укажите номер телефона');
  });

  it('меньше 10 цифр → "Введите не меньше 10 цифр номера"', () => {
    expect(validatePhoneField('9')).toBe('Введите не меньше 10 цифр номера');
    expect(validatePhoneField('+1234567')).toBe('Введите не меньше 10 цифр номера');
    expect(validatePhoneField('abc')).toBe('Введите не меньше 10 цифр номера');
  });

  it('больше 15 цифр → ошибка формата', () => {
    expect(validatePhoneField('+1234567890123456')).toBe(
      'Неверная длина или формат (с кодом страны — до 15 цифр)',
    );
  });

  it('валидные номера → null', () => {
    expect(validatePhoneField('+79991234567')).toBeNull();
    expect(validatePhoneField('89991234567')).toBeNull();
    expect(validatePhoneField('9991234567')).toBeNull();
    expect(validatePhoneField('+441234567890')).toBeNull();
  });
});

describe('validatePhoneFieldOptional', () => {
  it('пусто → null (поле необязательное)', () => {
    expect(validatePhoneFieldOptional('')).toBeNull();
    expect(validatePhoneFieldOptional('   ')).toBeNull();
  });

  it('невалид → та же ошибка, что у обязательного поля', () => {
    expect(validatePhoneFieldOptional('9')).toBe('Введите не меньше 10 цифр номера');
  });

  it('валидный → null', () => {
    expect(validatePhoneFieldOptional('+79991234567')).toBeNull();
  });
});

describe('normalizePhoneForApi', () => {
  it('пусто → null', () => {
    expect(normalizePhoneForApi('')).toBeNull();
    expect(normalizePhoneForApi('   ')).toBeNull();
  });

  it('валид → E.164', () => {
    expect(normalizePhoneForApi('8 (999) 123-45-67')).toBe('+79991234567');
  });

  it('невалид → null', () => {
    expect(normalizePhoneForApi('abc')).toBeNull();
    expect(normalizePhoneForApi('+12345')).toBeNull();
  });
});

describe('phoneErrorAfterBlur', () => {
  it('required + пусто → ошибка', () => {
    expect(phoneErrorAfterBlur('', true)).toBe('Укажите номер телефона');
  });

  it('optional + пусто → null', () => {
    expect(phoneErrorAfterBlur('', false)).toBeNull();
    expect(phoneErrorAfterBlur('   ', false)).toBeNull();
  });

  it('optional + невалид → ошибка', () => {
    expect(phoneErrorAfterBlur('9', false)).toBe('Введите не меньше 10 цифр номера');
  });

  it('required + валид → null', () => {
    expect(phoneErrorAfterBlur('+79991234567', true)).toBeNull();
  });
});

describe('sanitizePhoneInputRu (deprecated)', () => {
  it('делегирует processPhoneInputForDisplay', () => {
    expect(sanitizePhoneInputRu('89991234567')).toBe('+7 (999) 123-45-67');
    expect(sanitizePhoneInputRu('')).toBe('');
  });
});
