import { describe, expect, it } from 'vitest';
import { isTaskOverdue, taskDisplayStatus } from '../utils/taskDeadline';
import { TASK_STATUS_LABELS, isFinalTaskStatus, taskStatusLabel } from '../utils/taskStatus';

describe('task priority maps', () => {
  const PRIORITY_LABELS: Record<string, string> = { low: 'Низкий', medium: 'Средний', high: 'Высокий' };

  it.each(['low', 'medium', 'high'])('label for %s exists', (p) => {
    expect(PRIORITY_LABELS[p]).toBeTruthy();
  });

  it('unknown priority → undefined', () => {
    expect(PRIORITY_LABELS['xxx']).toBeUndefined();
  });
});

describe('task status maps', () => {
  it.each(['pending', 'in_progress', 'review', 'completed', 'rejected', 'overdue'])('label for %s', (s) => {
    expect(TASK_STATUS_LABELS[s]).toBeTruthy();
  });

  it('rejected → «Отклонено»', () => {
    expect(taskStatusLabel('rejected')).toBe('Отклонено');
  });

  it('all 6 statuses', () => expect(Object.keys(TASK_STATUS_LABELS)).toHaveLength(6));

  it('completed and rejected are final', () => {
    expect(isFinalTaskStatus('completed')).toBe(true);
    expect(isFinalTaskStatus('rejected')).toBe(true);
    expect(isFinalTaskStatus('in_progress')).toBe(false);
    expect(isFinalTaskStatus('overdue')).toBe(false);
  });
});

describe('task direction filter', () => {
  function getAssignedTo(direction: 'my' | 'from_uritech'): string {
    return direction === 'my' ? 'uritech' : 'partner';
  }

  it('my → uritech', () => expect(getAssignedTo('my')).toBe('uritech'));
  it('from_uritech → partner', () => expect(getAssignedTo('from_uritech')).toBe('partner'));
});

describe('overdue detection', () => {
  const now = Date.parse('2026-11-27T12:00:00Z');

  it('past date + pending → overdue', () => {
    expect(isTaskOverdue({ due_date: '2020-01-01', status: 'pending' }, now)).toBe(true);
  });

  it('future date + pending → not overdue', () => {
    expect(isTaskOverdue({ due_date: '2099-01-01', status: 'pending' }, now)).toBe(false);
  });

  it('past date + completed → not overdue', () => {
    expect(isTaskOverdue({ due_date: '2020-01-01', status: 'completed' }, now)).toBe(false);
  });

  it('past date + rejected → not overdue', () => {
    expect(isTaskOverdue({ due_date: '2020-01-01', status: 'rejected' }, now)).toBe(false);
  });

  it('rejected with a past exact deadline stays rejected, not overdue', () => {
    const task = { due_at: '2020-01-01T10:00:00Z', status: 'rejected' };
    expect(isTaskOverdue(task, now)).toBe(false);
    expect(taskDisplayStatus(task, now)).toBe('rejected');
  });
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
