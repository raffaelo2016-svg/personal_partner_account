import { describe, expect, it } from 'vitest';
import {
  CASE_NUMBER_MAX_LENGTH,
  isBlankCaseNumber,
  kadCaseUrl,
  normalizeCaseNumber,
  resolveCaseUrl,
  validateCaseNumber,
} from './courtCase';

const KAD_CARD = 'https://kad.arbitr.ru/Kad/Card';

describe('normalizeCaseNumber', () => {
  it('убирает пробелы и приводит к верхнему регистру', () => {
    expect(normalizeCaseNumber(' а66-5146 / 2026 ')).toBe('А66-5146/2026');
    expect(normalizeCaseNumber('А66\u00a0-\u00a05146/2026')).toBe('А66-5146/2026');
  });

  it('оставляет латинскую букву латинской — КАД понимает оба варианта', () => {
    expect(normalizeCaseNumber('a66-5146/2026')).toBe('A66-5146/2026');
  });

  it('возвращает пустую строку для пустых значений', () => {
    expect(normalizeCaseNumber('')).toBe('');
    expect(normalizeCaseNumber('   ')).toBe('');
    expect(normalizeCaseNumber(null)).toBe('');
    expect(normalizeCaseNumber(undefined)).toBe('');
  });
});

describe('isBlankCaseNumber', () => {
  it('считает пустыми пустую строку и заглушки', () => {
    expect(isBlankCaseNumber('')).toBe(true);
    expect(isBlankCaseNumber('   ')).toBe(true);
    expect(isBlankCaseNumber('—')).toBe(true);
    expect(isBlankCaseNumber('-')).toBe(true);
    expect(isBlankCaseNumber('–')).toBe(true);
    expect(isBlankCaseNumber(null)).toBe(true);
  });

  it('не считает пустым настоящий номер', () => {
    expect(isBlankCaseNumber('А66-5146/2026')).toBe(false);
  });
});

describe('kadCaseUrl', () => {
  it('строит ссылку на карточку дела по номеру', () => {
    expect(kadCaseUrl('А66-5146/2026')).toBe(`${KAD_CARD}?number=%D0%9066-5146%2F2026`);
  });

  it('нормализует номер перед подстановкой в ссылку', () => {
    expect(kadCaseUrl(' а66-5146/2026 ')).toBe(`${KAD_CARD}?number=%D0%9066-5146%2F2026`);
  });

  it('возвращает null без номера дела', () => {
    expect(kadCaseUrl('')).toBeNull();
    expect(kadCaseUrl('—')).toBeNull();
    expect(kadCaseUrl(null)).toBeNull();
  });
});

describe('resolveCaseUrl', () => {
  const guidUrl = 'https://kad.arbitr.ru/Card/eb01b4c8-c6bb-4d57-af07-52494311980d';

  it('предпочитает сохранённую ссылку на КАД', () => {
    expect(resolveCaseUrl('А66-5146/2026', guidUrl)).toBe(guidUrl);
  });

  it('строит ссылку из номера, если сохранённой нет', () => {
    expect(resolveCaseUrl('А66-5146/2026', null)).toBe(`${KAD_CARD}?number=%D0%9066-5146%2F2026`);
  });

  it('игнорирует небезопасные и чужие URL', () => {
    expect(resolveCaseUrl('А66-5146/2026', 'javascript:alert(1)')).toBe(
      `${KAD_CARD}?number=%D0%9066-5146%2F2026`,
    );
    expect(resolveCaseUrl('А66-5146/2026', 'https://evil.example/kad')).toBe(
      `${KAD_CARD}?number=%D0%9066-5146%2F2026`,
    );
    expect(resolveCaseUrl('А66-5146/2026', 'http://kad.arbitr.ru/Card/1')).toBe(
      `${KAD_CARD}?number=%D0%9066-5146%2F2026`,
    );
  });

  it('возвращает null, если нет ни ссылки, ни номера', () => {
    expect(resolveCaseUrl('', 'https://evil.example/kad')).toBeNull();
  });
});

describe('validateCaseNumber', () => {
  it('пропускает корректный номер в любом регистре и с пробелами', () => {
    expect(validateCaseNumber('А66-5146/2026')).toBeNull();
    expect(validateCaseNumber(' а66-5146 / 2026 ')).toBeNull();
  });

  it('разрешает пустое значение — так номер удаляют', () => {
    expect(validateCaseNumber('')).toBeNull();
    expect(validateCaseNumber('   ')).toBeNull();
    expect(validateCaseNumber(null)).toBeNull();
  });

  it('требует хотя бы одну цифру', () => {
    expect(validateCaseNumber('дело')).toBe('В номере дела должны быть цифры');
  });

  it('ограничивает длину после нормализации', () => {
    expect(validateCaseNumber('А'.repeat(CASE_NUMBER_MAX_LENGTH + 1))).toBe(
      `Номер дела длиннее ${CASE_NUMBER_MAX_LENGTH} символов`,
    );
  });
});
