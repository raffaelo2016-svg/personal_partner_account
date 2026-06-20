import { describe, expect, it } from 'vitest';

describe('formatMoney', () => {
  function formatMoney(kopecks: number): string {
    return (kopecks / 100).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ₽';
  }

  it('0 → 0 ₽', () => expect(formatMoney(0)).toBe('0 ₽'));
  it('100 → 1 ₽', () => expect(formatMoney(100)).toBe('1 ₽'));
  it('1500000 → 15 000 ₽', () => expect(formatMoney(1500000)).toMatch(/15[\s\u00a0]000 ₽/));
  it('negative', () => expect(formatMoney(-500)).toMatch(/-5 ₽/));
});

describe('court fee status', () => {
  const FEE_STATUS: Record<string, { label: string; color: string }> = {
    unpaid: { label: 'Не оплачено', color: 'yellow' },
    paid: { label: 'Оплачено', color: 'green' },
    overdue: { label: 'Просрочено', color: 'red' },
  };

  it.each(['unpaid', 'paid', 'overdue'])('%s has label and color', (s) => {
    expect(FEE_STATUS[s].label).toBeTruthy();
    expect(FEE_STATUS[s].color).toBeTruthy();
  });

  it('3 statuses total', () => expect(Object.keys(FEE_STATUS)).toHaveLength(3));
});

describe('debt banner logic', () => {
  function shouldShowBanner(totalDebt: number, overdue: boolean): boolean {
    return totalDebt > 0;
  }

  it('no debt → hide', () => expect(shouldShowBanner(0, false)).toBe(false));
  it('has debt → show', () => expect(shouldShowBanner(1500, false)).toBe(true));
  it('overdue debt → show', () => expect(shouldShowBanner(1500, true)).toBe(true));
});
