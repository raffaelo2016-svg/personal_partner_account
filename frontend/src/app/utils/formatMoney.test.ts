import { describe, expect, it } from 'vitest';
import { formatMoney } from './formatMoney';

describe('formatMoney', () => {
  it('форматирует 0 копеек', () => {
    expect(formatMoney(0)).toMatch(/^0\s₽$/);
  });

  it('форматирует 100 копеек → 1 ₽', () => {
    expect(formatMoney(100)).toMatch(/^1\s₽$/);
  });

  it('форматирует крупную сумму с группировкой тысяч', () => {
    const out = formatMoney(1_500_000);
    expect(out).toMatch(/15\s000/);
    expect(out).toMatch(/\s₽$/);
  });

  it('сохраняет дробные копейки', () => {
    const out = formatMoney(99);
    expect(out).toMatch(/0[.,]99/);
    expect(out).toMatch(/\s₽$/);
  });

  it('округляет до двух знаков после запятой', () => {
    const out = formatMoney(123);
    expect(out).toMatch(/1[.,]23/);
  });

  it('обрабатывает отрицательные суммы', () => {
    const out = formatMoney(-10_000);
    expect(out.startsWith('-')).toBe(true);
    expect(out).toMatch(/100/);
  });

  it('не падает на очень больших числах', () => {
    expect(() => formatMoney(Number.MAX_SAFE_INTEGER)).not.toThrow();
    expect(formatMoney(Number.MAX_SAFE_INTEGER)).toMatch(/\s₽$/);
  });

  it('не добавляет дробную часть для целых рублей', () => {
    expect(formatMoney(5000)).not.toMatch(/[.,]/);
  });
});
