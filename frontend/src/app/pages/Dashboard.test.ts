import { describe, expect, it } from 'vitest';

describe('dashboard stats computation', () => {
  interface Stats { total_clients: number; before_court: number; in_court: number; completed: number; new_this_week: number }

  function isDataLoaded(stats: Stats | undefined): boolean {
    return stats !== undefined && stats.total_clients >= 0;
  }

  it('undefined → not loaded', () => expect(isDataLoaded(undefined)).toBe(false));
  it('valid → loaded', () => expect(isDataLoaded({ total_clients: 0, before_court: 0, in_court: 0, completed: 0, new_this_week: 0 })).toBe(true));
});

describe('task completion ring', () => {
  function completionPercent(completed: number, total: number): number {
    return total === 0 ? 0 : Math.round((completed / total) * 100);
  }

  it('0/0 → 0', () => expect(completionPercent(0, 0)).toBe(0));
  it('3/10 → 30', () => expect(completionPercent(3, 10)).toBe(30));
  it('10/10 → 100', () => expect(completionPercent(10, 10)).toBe(100));
});

describe('overdue debt alert', () => {
  function shouldShowAlert(overdueDebt: number, currentDebt: number): boolean {
    return overdueDebt > 0 || currentDebt > 0;
  }

  it('no debt → hide', () => expect(shouldShowAlert(0, 0)).toBe(false));
  it('overdue → show', () => expect(shouldShowAlert(100, 0)).toBe(true));
  it('current → show', () => expect(shouldShowAlert(0, 100)).toBe(true));
  it('both → show', () => expect(shouldShowAlert(100, 200)).toBe(true));
});

describe('recent clients list', () => {
  function getTypeLabel(type: string): string {
    return type === 'before_court' ? 'ДО подачи в суд' : 'УЖЕ в суде';
  }

  it('before_court', () => expect(getTypeLabel('before_court')).toBe('ДО подачи в суд'));
  it('in_court', () => expect(getTypeLabel('in_court')).toBe('УЖЕ в суде'));
});
