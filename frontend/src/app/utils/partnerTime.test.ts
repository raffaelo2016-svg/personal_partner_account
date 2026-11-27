import { describe, expect, it } from 'vitest';

import { formatPartnerTime, timezoneForRegion, utcOffsetLabel } from './partnerTime';

describe('timezoneForRegion', () => {
  it('maps a known region to its timezone', () => {
    // Бэкенд группирует регионы UTC+7 под Asia/Novosibirsk — время совпадает.
    expect(timezoneForRegion('Красноярский край')).toBe('Asia/Novosibirsk');
    expect(timezoneForRegion('Москва')).toBe('Europe/Moscow');
  });

  it('falls back to Moscow when the region is empty', () => {
    expect(timezoneForRegion(null)).toBe('Europe/Moscow');
    expect(timezoneForRegion('   ')).toBe('Europe/Moscow');
  });

  it('falls back to Moscow for an unknown region', () => {
    expect(timezoneForRegion('Марс')).toBe('Europe/Moscow');
  });
});

describe('formatPartnerTime', () => {
  it('renders Moscow wall-clock time', () => {
    const date = new Date('2026-11-27T18:34:00Z');
    expect(formatPartnerTime(date, 'Europe/Moscow')).toBe('21:34');
  });

  it('renders a far-east timezone', () => {
    const date = new Date('2026-11-27T18:34:00Z');
    expect(formatPartnerTime(date, 'Asia/Kamchatka')).toBe('06:34');
  });

  it('falls back to Moscow for an invalid timezone', () => {
    const date = new Date('2026-11-27T18:34:00Z');
    expect(formatPartnerTime(date, 'Nope/Nowhere')).toBe('21:34');
  });
});

describe('utcOffsetLabel', () => {
  it('renders positive offsets', () => {
    expect(utcOffsetLabel(new Date('2026-11-27T18:34:00Z'), 'Europe/Moscow')).toBe('UTC+3');
    expect(utcOffsetLabel(new Date('2026-11-27T18:34:00Z'), 'Asia/Krasnoyarsk')).toBe('UTC+7');
  });

  it('accounts for daylight saving time', () => {
    expect(utcOffsetLabel(new Date('2026-07-01T12:00:00Z'), 'Europe/Berlin')).toBe('UTC+2');
    expect(utcOffsetLabel(new Date('2026-01-01T12:00:00Z'), 'Europe/Berlin')).toBe('UTC+1');
  });

  it('renders negative offsets', () => {
    // В ноябре в Нью-Йорке стандартное время: UTC−5.
    expect(utcOffsetLabel(new Date('2026-11-27T18:34:00Z'), 'America/New_York')).toBe('UTC-5');
  });

  it('falls back to Moscow for an invalid timezone', () => {
    expect(utcOffsetLabel(new Date('2026-11-27T18:34:00Z'), 'Nope/Nowhere')).toBe('UTC+3');
  });
});
