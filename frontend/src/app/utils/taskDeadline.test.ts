import { describe, expect, it } from 'vitest';
import {
  formatTaskDeadline, isTaskOverdue, taskDeadlineFields,
  taskDeadlinePayload, taskDeadlineTimestamp, taskDisplayStatus,
} from './taskDeadline';

describe('task deadlines in Moscow time', () => {
  it('treats a date-only deadline as the end of that Moscow day', () => {
    const task = { due_date: '2026-10-15', status: 'pending' };
    expect(taskDeadlineTimestamp(task)).toBe(Date.parse('2026-10-15T20:59:59.999Z'));
    expect(isTaskOverdue(task, Date.parse('2026-10-15T20:59:59Z'))).toBe(false);
    expect(isTaskOverdue(task, Date.parse('2026-10-15T21:00:00Z'))).toBe(true);
  });

  it('uses the exact deadline in preference to the calendar date', () => {
    const task = { due_date: '2026-10-15', due_at: '2026-10-15T09:30:00Z', status: 'in_progress' };
    expect(isTaskOverdue(task, Date.parse('2026-10-15T09:29:59Z'))).toBe(false);
    expect(isTaskOverdue(task, Date.parse('2026-10-15T09:30:01Z'))).toBe(true);
    expect(formatTaskDeadline(task)).toBe('15.10.2026, 12:30 МСК');
  });

  it('never marks completed or undated tasks overdue', () => {
    const now = Date.parse('2026-10-15T12:00:00Z');
    expect(isTaskOverdue({ due_at: '2026-01-01T00:00:00Z', status: 'completed' }, now)).toBe(false);
    expect(isTaskOverdue({ due_date: null, due_at: null, status: 'overdue' }, now)).toBe(false);
    expect(formatTaskDeadline({ due_date: null, due_at: null })).toBe('Без срока');
  });

  it('does not retain stale overdue presentation after moving or removing a deadline', () => {
    const now = Date.parse('2026-10-15T12:00:00Z');
    expect(taskDisplayStatus({ status: 'overdue', due_date: '2026-10-16' }, now)).toBe('pending');
    expect(taskDisplayStatus({ status: 'overdue', due_date: null }, now)).toBe('pending');
    expect(taskDisplayStatus({ status: 'in_progress', due_at: '2026-10-15T11:59:00Z' }, now)).toBe('overdue');
  });

  it('converts Moscow form values independently of the browser time zone, across midnight', () => {
    expect(taskDeadlinePayload('2026-10-15', '00:30')).toEqual({
      due_date: '2026-10-15', due_at: '2026-10-14T21:30:00.000Z',
    });
    expect(taskDeadlineFields({ due_date: '2026-10-14', due_at: '2026-10-14T21:30:00Z' })).toEqual({
      due_date: '2026-10-15', due_time: '00:30',
    });
  });

  it('preserves legacy calendar dates and explicitly clears both deadline fields', () => {
    expect(taskDeadlineFields({ due_date: '2026-10-15' })).toEqual({ due_date: '2026-10-15', due_time: '' });
    expect(taskDeadlinePayload('2026-10-15', '')).toEqual({ due_date: '2026-10-15', due_at: null });
    expect(taskDeadlinePayload('', '')).toEqual({ due_date: null, due_at: null });
    expect(formatTaskDeadline({ due_date: '2026-10-15' })).toBe('15.10.2026, до конца дня (МСК)');
  });
});
