import { describe, expect, it } from 'vitest';
import { formatTimeInTimezone, getTimezoneMeta } from './timezones';

describe('timezone metadata', () => {
  it('returns short label and offset for known zones', () => {
    expect(getTimezoneMeta('Asia/Yekaterinburg')).toEqual({ short: 'ЕКБ', offset: 'UTC+5' });
    expect(getTimezoneMeta('Europe/Moscow')).toEqual({ short: 'МСК', offset: 'UTC+3' });
  });

  it('falls back to Moscow for missing or unknown zones', () => {
    expect(getTimezoneMeta(null)).toEqual({ short: 'МСК', offset: 'UTC+3' });
    expect(getTimezoneMeta('Unknown/Zone')).toEqual({ short: 'МСК', offset: 'UTC+3' });
  });

  it('formats time in the requested timezone', () => {
    const date = new Date('2026-11-02T06:45:00Z');
    expect(formatTimeInTimezone('Europe/Moscow', date)).toBe('09:45');
    expect(formatTimeInTimezone('Asia/Yekaterinburg', date)).toBe('11:45');
  });
});
