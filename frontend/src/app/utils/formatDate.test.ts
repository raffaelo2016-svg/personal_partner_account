import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  formatDate,
  formatDateShort,
  formatDateTime,
  formatRelative,
  formatTime,
} from './formatDate';

const ISO = '2026-04-13T14:30:00Z';
const TZ = 'Europe/Moscow';

describe('formatDate', () => {
  it('formats full date in Russian', () => {
    const result = formatDate(ISO, TZ);
    expect(result).toMatch(/13/);
    expect(result).toMatch(/апреля/i);
    expect(result).toMatch(/2026/);
  });

  it('returns — for empty', () => expect(formatDate('', TZ)).toBe('—'));
  it('returns — for invalid', () => expect(formatDate('not-a-date', TZ)).toBe('—'));
});

describe('formatDateShort', () => {
  it('formats as DD.MM.YYYY', () => {
    const result = formatDateShort(ISO, TZ);
    expect(result).toMatch(/13\.04\.2026/);
  });

  it('returns — for empty', () => expect(formatDateShort('')).toBe('—'));
  it('returns — for invalid', () => expect(formatDateShort('xxx')).toBe('—'));
});

describe('formatDateTime', () => {
  it('includes date and time', () => {
    const result = formatDateTime(ISO, TZ);
    expect(result).toMatch(/13\.04\.2026/);
    expect(result).toMatch(/17:30/); // UTC+3
  });

  it('returns — for empty', () => expect(formatDateTime('')).toBe('—'));
});

describe('formatTime', () => {
  it('formats HH:MM', () => {
    const result = formatTime(ISO, TZ);
    expect(result).toMatch(/17:30/); // UTC+3
  });

  it('returns — for empty', () => expect(formatTime('')).toBe('—'));
  it('returns — for invalid', () => expect(formatTime('xxx')).toBe('—'));
});

describe('timezone handling', () => {
  it('different tz gives different time', () => {
    const moscow = formatTime(ISO, 'Europe/Moscow');
    const tokyo = formatTime(ISO, 'Asia/Tokyo');
    expect(moscow).not.toBe(tokyo);
  });

  // Бэкенд сериализует naive UTC без 'Z' — строка без TZ-суффикса
  // должна трактоваться как UTC, а не как local-time браузера.
  it('naive datetime without TZ parsed as UTC', () => {
    const naive = '2026-04-13T14:30:00';
    expect(formatTime(naive, 'Europe/Moscow')).toBe(formatTime(ISO, 'Europe/Moscow'));
    expect(formatDateTime(naive, 'Europe/Moscow')).toBe(formatDateTime(ISO, 'Europe/Moscow'));
  });
});

describe('formatRelative', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-20T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('час назад', () => {
    const out = formatRelative('2026-04-20T11:00:00Z');
    expect(out).toMatch(/назад/);
    expect(out).toMatch(/час/i);
  });

  it('через два дня', () => {
    const out = formatRelative('2026-04-22T12:00:00Z');
    expect(out).toMatch(/через/);
    expect(out).toMatch(/2\s+дн/i);
  });

  it('несколько минут назад', () => {
    const out = formatRelative('2026-04-20T11:55:00Z');
    expect(out).toMatch(/назад/);
    expect(out).toMatch(/мин/i);
  });

  it('локаль русская (ru)', () => {
    const out = formatRelative('2026-04-10T12:00:00Z');
    expect(out).toMatch(/[а-я]/i);
  });
});
