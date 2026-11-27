import { describe, expect, it } from 'vitest';

import { REGION_TIMEZONES } from '@/app/data/regionTimezones';
import { REGION_GROUPS } from '@/app/data/arbitrageCourts';

const frontendRegions = REGION_GROUPS.flatMap((group) => group.regions.map((region) => region.name));

describe('region → timezone mapping', () => {
  it('covers every region from REGION_GROUPS', () => {
    const missing = frontendRegions.filter((region) => !(region in REGION_TIMEZONES));
    expect(missing).toEqual([]);
  });

  it('has no regions outside REGION_GROUPS', () => {
    const known = new Set(frontendRegions);
    const extra = Object.keys(REGION_TIMEZONES).filter((region) => !known.has(region));
    expect(extra).toEqual([]);
  });

  it('uses valid IANA zones', () => {
    for (const timeZone of Object.values(REGION_TIMEZONES)) {
      expect(() => new Intl.DateTimeFormat('ru-RU', { timeZone })).not.toThrow();
    }
  });
});
