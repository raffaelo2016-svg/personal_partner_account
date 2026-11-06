import { describe, expect, it } from 'vitest';

import {
  formatPauseDays,
  partnerPauseHint,
  partnerPauseTone,
  PARTNER_PAUSE_BLUE_AFTER_DAYS,
  PARTNER_PAUSE_RED_AFTER_DAYS,
} from '../partnerPause';

describe('partnerPauseTone', () => {
  it('меньше порога — без подсветки', () => {
    expect(partnerPauseTone(0)).toBe('neutral');
    expect(partnerPauseTone(14)).toBe('neutral');
    expect(partnerPauseTone(15)).toBe('neutral');
  });

  it('больше 15 дней — синий', () => {
    expect(partnerPauseTone(16)).toBe('blue');
    expect(partnerPauseTone(30)).toBe('blue');
  });

  it('больше 30 дней — красный', () => {
    expect(partnerPauseTone(31)).toBe('red');
    expect(partnerPauseTone(365)).toBe('red');
  });

  it('пороги совпадают с константами', () => {
    expect(partnerPauseTone(PARTNER_PAUSE_BLUE_AFTER_DAYS + 1)).toBe('blue');
    expect(partnerPauseTone(PARTNER_PAUSE_RED_AFTER_DAYS + 1)).toBe('red');
    expect(partnerPauseTone(PARTNER_PAUSE_RED_AFTER_DAYS)).not.toBe('red');
  });
});

describe('formatPauseDays', () => {
  it.each([
    [1, '1 день'],
    [2, '2 дня'],
    [4, '4 дня'],
    [5, '5 дней'],
    [11, '11 дней'],
    [14, '14 дней'],
    [21, '21 день'],
    [22, '22 дня'],
    [25, '25 дней'],
    [31, '31 день'],
    [101, '101 день'],
  ])('%i → %s', (days, expected) => {
    expect(formatPauseDays(days)).toBe(expected);
  });
});

describe('partnerPauseHint', () => {
  it('помечает критичные паузы', () => {
    expect(partnerPauseHint(45)).toContain('критично');
    expect(partnerPauseHint(20)).toContain('пора напомнить');
    expect(partnerPauseHint(10)).not.toContain('критично');
  });
});
