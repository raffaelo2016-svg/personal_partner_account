import { describe, expect, it } from 'vitest';

describe('task priority maps', () => {
  const PRIORITY_LABELS: Record<string, string> = { low: 'Низкий', medium: 'Средний', high: 'Высокий' };
  const PRIORITY_COLORS: Record<string, string> = { low: 'bg-gray', medium: 'bg-yellow', high: 'bg-red' };

  it.each(['low', 'medium', 'high'])('label for %s exists', (p) => {
    expect(PRIORITY_LABELS[p]).toBeTruthy();
  });

  it('unknown priority → undefined', () => {
    expect(PRIORITY_LABELS['xxx']).toBeUndefined();
  });
});

describe('task status maps', () => {
  const STATUS_LABELS: Record<string, string> = {
    pending: 'Ожидает', in_progress: 'В работе', completed: 'Завершена', overdue: 'Просрочена',
  };

  it.each(['pending', 'in_progress', 'completed', 'overdue'])('label for %s', (s) => {
    expect(STATUS_LABELS[s]).toBeTruthy();
  });

  it('all 4 statuses', () => expect(Object.keys(STATUS_LABELS)).toHaveLength(4));
});

describe('task direction filter', () => {
  function getAssignedTo(direction: 'my' | 'from_uritech'): string {
    return direction === 'my' ? 'partner' : 'uritech';
  }

  it('my → partner', () => expect(getAssignedTo('my')).toBe('partner'));
  it('from_uritech → uritech', () => expect(getAssignedTo('from_uritech')).toBe('uritech'));
});

describe('overdue detection', () => {
  function isOverdue(dueDate: string, status: string): boolean {
    if (status === 'completed') return false;
    return new Date(dueDate) < new Date();
  }

  it('past date + pending → overdue', () => expect(isOverdue('2020-01-01', 'pending')).toBe(true));
  it('future date + pending → not overdue', () => expect(isOverdue('2099-01-01', 'pending')).toBe(false));
  it('past date + completed → not overdue', () => expect(isOverdue('2020-01-01', 'completed')).toBe(false));
});

describe('completion percent', () => {
  function calcPercent(completed: number, total: number): number {
    return total === 0 ? 0 : Math.round((completed / total) * 100);
  }

  it('0/0 → 0', () => expect(calcPercent(0, 0)).toBe(0));
  it('5/10 → 50', () => expect(calcPercent(5, 10)).toBe(50));
  it('10/10 → 100', () => expect(calcPercent(10, 10)).toBe(100));
  it('1/3 → 33', () => expect(calcPercent(1, 3)).toBe(33));
});
