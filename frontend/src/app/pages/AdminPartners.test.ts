import { describe, expect, it } from 'vitest';
import { PARTNER_STATUS_LABELS, PARTNER_STATUS_COLORS } from '../data/statusMaps';

describe('partner status labels', () => {
  it.each(['pending', 'active', 'blocked'])('%s has label', (s) => {
    expect(PARTNER_STATUS_LABELS[s]).toBeTruthy();
  });

  it('pending → На проверке', () => expect(PARTNER_STATUS_LABELS['pending']).toBe('На проверке'));
  it('active → Активный', () => expect(PARTNER_STATUS_LABELS['active']).toBe('Активный'));
  it('blocked → Заблокирован', () => expect(PARTNER_STATUS_LABELS['blocked']).toBe('Заблокирован'));
  it('unknown → undefined', () => expect(PARTNER_STATUS_LABELS['xxx']).toBeUndefined());
});

describe('partner status colors', () => {
  it.each(['pending', 'active', 'blocked'])('%s has color', (s) => {
    expect(PARTNER_STATUS_COLORS[s]).toBeTruthy();
  });

  it('active contains green', () => expect(PARTNER_STATUS_COLORS['active']).toContain('green'));
  it('blocked contains red', () => expect(PARTNER_STATUS_COLORS['blocked']).toContain('red'));
});

describe('partner initials', () => {
  function getInitials(name: string): string {
    return name.slice(0, 2).toUpperCase();
  }

  it('short name', () => expect(getInitials('ООО')).toBe('ОО'));
  it('single char', () => expect(getInitials('A')).toBe('A'));
  it('empty', () => expect(getInitials('')).toBe(''));
  it('latin', () => expect(getInitials('Test Co')).toBe('TE'));
});

describe('partner search filter', () => {
  function matchesSearch(companyName: string, search: string): boolean {
    return companyName.toLowerCase().includes(search.toLowerCase());
  }

  it('exact match', () => expect(matchesSearch('Test Co', 'Test')).toBe(true));
  it('case insensitive', () => expect(matchesSearch('Test Co', 'test')).toBe(true));
  it('no match', () => expect(matchesSearch('Test Co', 'xyz')).toBe(false));
  it('empty search → true', () => expect(matchesSearch('Test', '')).toBe(true));
});

describe('partner stats computation', () => {
  function activeRate(active: number, total: number): number {
    return total === 0 ? 0 : Math.round((active / total) * 100);
  }

  it('0/0 → 0', () => expect(activeRate(0, 0)).toBe(0));
  it('5/10 → 50', () => expect(activeRate(5, 10)).toBe(50));
  it('10/10 → 100', () => expect(activeRate(10, 10)).toBe(100));
});
