import { describe, expect, it } from 'vitest';
import {
  flattenZodErrors,
  registrationStep1Schema,
  registrationStep2Schema,
} from './registration';

describe('registrationStep1Schema', () => {
  const valid = {
    companyName: 'ООО Ромашка',
    inn: '1234567890',
    ogrn: '1234567890123',
    legalAddress: 'г. Москва',
    courtFee: '1500',
    paymentTermDays: '10',
  };

  it('accepts valid input', () => {
    expect(registrationStep1Schema.safeParse(valid).success).toBe(true);
  });

  it('rejects INN with wrong length', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, inn: '123' });
    expect(result.success).toBe(false);
    expect(flattenZodErrors(result).inn).toBe('ИНН должен содержать 10 цифр');
  });

  it('rejects OGRN with wrong length', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, ogrn: '123' });
    expect(flattenZodErrors(result).ogrn).toBe('ОГРН должен содержать 13 цифр');
  });

  it('rejects zero courtFee', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, courtFee: '0' });
    expect(flattenZodErrors(result).courtFee).toBe('Сумма должна быть больше 0');
  });

  it('reports multiple errors at once', () => {
    const result = registrationStep1Schema.safeParse({
      companyName: '',
      inn: '',
      ogrn: '',
      legalAddress: '',
      courtFee: '',
      paymentTermDays: '',
    });
    const errors = flattenZodErrors(result);
    expect(Object.keys(errors).length).toBe(6);
  });

  it('rejects zero paymentTermDays', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, paymentTermDays: '0' });
    expect(flattenZodErrors(result).paymentTermDays).toBe('Срок должен быть больше 0');
  });

  it('rejects non-numeric courtFee as "больше 0"', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, courtFee: 'abc' });
    expect(flattenZodErrors(result).courtFee).toBe('Сумма должна быть больше 0');
  });

  it('rejects negative courtFee', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, courtFee: '-100' });
    expect(flattenZodErrors(result).courtFee).toBe('Сумма должна быть больше 0');
  });

  it('rejects INN with non-digit characters', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, inn: '12345abc90' });
    expect(flattenZodErrors(result).inn).toBe('ИНН должен содержать 10 цифр');
  });

  it('rejects INN with 11 digits', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, inn: '12345678901' });
    expect(flattenZodErrors(result).inn).toBe('ИНН должен содержать 10 цифр');
  });

  it('rejects OGRN with 14 digits', () => {
    const result = registrationStep1Schema.safeParse({ ...valid, ogrn: '12345678901234' });
    expect(flattenZodErrors(result).ogrn).toBe('ОГРН должен содержать 13 цифр');
  });
});

describe('registrationStep2Schema', () => {
  const valid = {
    contactName: 'Иван Иванов',
    contactEmail: 'ivan@example.com',
    password: 'secret123',
    confirmPassword: 'secret123',
    agreeTerms: true as const,
    agreePersonalData: true as const,
  };

  it('accepts valid input', () => {
    expect(registrationStep2Schema.safeParse(valid).success).toBe(true);
  });

  it('rejects mismatched passwords', () => {
    const result = registrationStep2Schema.safeParse({ ...valid, confirmPassword: 'other' });
    expect(flattenZodErrors(result).confirmPassword).toBe('Пароли не совпадают');
  });

  it('rejects short password', () => {
    const result = registrationStep2Schema.safeParse({
      ...valid,
      password: 'short',
      confirmPassword: 'short',
    });
    expect(flattenZodErrors(result).password).toBe('Минимум 8 символов');
  });

  it('requires agreeTerms', () => {
    const result = registrationStep2Schema.safeParse({ ...valid, agreeTerms: false });
    expect(flattenZodErrors(result).agreeTerms).toBe('Необходимо согласие');
  });

  it('rejects invalid email', () => {
    const result = registrationStep2Schema.safeParse({ ...valid, contactEmail: 'not-an-email' });
    expect(flattenZodErrors(result).contactEmail).toBe('Некорректный email');
  });

  it('requires agreePersonalData', () => {
    const result = registrationStep2Schema.safeParse({ ...valid, agreePersonalData: false });
    expect(flattenZodErrors(result).agreePersonalData).toBe('Необходимо согласие');
  });

  it('empty password reports "Обязательное поле" (not length)', () => {
    const result = registrationStep2Schema.safeParse({
      ...valid,
      password: '',
      confirmPassword: '',
    });
    expect(flattenZodErrors(result).password).toBe('Обязательное поле');
  });

  it('password exactly 8 chars passes', () => {
    const result = registrationStep2Schema.safeParse({
      ...valid,
      password: '12345678',
      confirmPassword: '12345678',
    });
    expect(result.success).toBe(true);
  });

  it('empty contactEmail reports "Обязательное поле"', () => {
    const result = registrationStep2Schema.safeParse({ ...valid, contactEmail: '' });
    expect(flattenZodErrors(result).contactEmail).toBe('Обязательное поле');
  });
});

describe('flattenZodErrors', () => {
  it('returns empty object for successful parse', () => {
    const valid = {
      companyName: 'ООО Ромашка',
      inn: '1234567890',
      ogrn: '1234567890123',
      legalAddress: 'г. Москва',
      courtFee: '1500',
      paymentTermDays: '10',
    };
    const result = registrationStep1Schema.safeParse(valid);
    expect(flattenZodErrors(result)).toEqual({});
  });

  it('keeps only first issue per field', () => {
    const result = registrationStep1Schema.safeParse({
      companyName: 'ок',
      inn: 'abc',
      ogrn: '1234567890123',
      legalAddress: 'ок',
      courtFee: '100',
      paymentTermDays: '1',
    });
    const errors = flattenZodErrors(result);
    expect(Object.keys(errors)).toEqual(['inn']);
  });
});
