import { describe, expect, it } from 'vitest';
import { clientFormSchema } from '../schemas/client';
import { getStatusLabel, getStatusBadgeColor, getStatusDotColor, STATUS_LABELS } from '../data/statusMaps';

// ══════════════════════════════════════════════════════════
// 1. ZOD SCHEMA — clientFormSchema
// ══════════════════════════════════════════════════════════

describe('clientFormSchema', () => {
  it('accepts valid fullName', () => {
    expect(clientFormSchema.safeParse({ fullName: 'Иванов' }).success).toBe(true);
  });

  it('rejects empty fullName', () => {
    expect(clientFormSchema.safeParse({ fullName: '' }).success).toBe(false);
  });

  it('rejects missing fullName', () => {
    expect(clientFormSchema.safeParse({}).success).toBe(false);
  });

  it('accepts valid email', () => {
    expect(clientFormSchema.safeParse({ fullName: 'X', email: 'a@b.com' }).success).toBe(true);
  });

  it('rejects invalid email', () => {
    const r = clientFormSchema.safeParse({ fullName: 'X', email: 'not-email' });
    expect(r.success).toBe(false);
  });

  it('accepts empty email (optional)', () => {
    expect(clientFormSchema.safeParse({ fullName: 'X', email: '' }).success).toBe(true);
  });

  it('accepts unicode in fullName', () => {
    expect(clientFormSchema.safeParse({ fullName: "José O'Brien" }).success).toBe(true);
  });

  it('accepts single char fullName', () => {
    expect(clientFormSchema.safeParse({ fullName: 'Я' }).success).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════
// 2. STATUS MAPS — labels, colors
// ══════════════════════════════════════════════════════════

describe('getStatusLabel', () => {
  it.each([
    ['documents_collection', 'Сбор документов'],
    ['documents_formation', 'Формирование документов'],
    ['sent_to_court', 'Отправка в суд'],
    ['documents_decision', 'Документы приняты / не приняты'],
    ['waiting_hearing', 'Ожидание заседания'],
    ['restructuring', 'Реструктуризация'],
    ['auction', 'Торги'],
    ['realization', 'Реализация'],
    ['completed', 'Завершено'],
  ])('maps %s → %s', (status, label) => {
    expect(getStatusLabel(status)).toBe(label);
  });

  it('returns raw status for unknown', () => {
    expect(getStatusLabel('unknown_status')).toBe('unknown_status');
  });

  it('returns empty string for empty input', () => {
    expect(getStatusLabel('')).toBe('');
  });
});

describe('getStatusBadgeColor', () => {
  it('returns color for known status', () => {
    expect(getStatusBadgeColor('documents_collection')).toContain('bg-blue');
  });

  it('returns gray for unknown status', () => {
    expect(getStatusBadgeColor('xxx')).toContain('bg-gray');
  });
});

describe('getStatusDotColor', () => {
  it('returns dot color for known status', () => {
    expect(getStatusDotColor('auction')).toContain('bg-amber');
  });

  it('returns gray for unknown', () => {
    expect(getStatusDotColor('xxx')).toContain('bg-gray');
  });
});

describe('STATUS_LABELS completeness', () => {
  const ALL_STATUSES = [
    'documents_collection', 'documents_formation', 'sent_to_court',
    'documents_decision', 'waiting_hearing', 'restructuring', 'auction', 'realization', 'completed',
  ];

  it('has labels for all 9 statuses', () => {
    for (const s of ALL_STATUSES) {
      expect(STATUS_LABELS[s]).toBeTruthy();
    }
  });
});

// ══════════════════════════════════════════════════════════
// 3. CLIENT CATEGORY LOGIC
// ══════════════════════════════════════════════════════════

describe('category classification', () => {
  const BEFORE_COURT = ['documents_collection', 'documents_formation', 'sent_to_court', 'documents_decision'];
  const IN_COURT = ['waiting_hearing', 'restructuring', 'auction'];
  const COMPLETED = ['realization', 'completed'];

  function getCategory(status: string): string {
    if (BEFORE_COURT.includes(status)) return 'before_court';
    if (IN_COURT.includes(status)) return 'in_court';
    if (COMPLETED.includes(status)) return 'completed';
    return 'unknown';
  }

  it.each([
    ['documents_collection', 'before_court'],
    ['documents_formation', 'before_court'],
    ['sent_to_court', 'before_court'],
    ['documents_decision', 'before_court'],
    ['waiting_hearing', 'in_court'],
    ['restructuring', 'in_court'],
    ['auction', 'in_court'],
    ['realization', 'completed'],
    ['completed', 'completed'],
  ])('%s → %s', (status, category) => {
    expect(getCategory(status)).toBe(category);
  });

  it('unknown status → unknown', () => {
    expect(getCategory('xxx')).toBe('unknown');
  });
});

// ══════════════════════════════════════════════════════════
// 4. PROGRESS CALCULATION
// ══════════════════════════════════════════════════════════

describe('progress calculation', () => {
  const STATUS_ORDER = [
    'documents_collection', 'documents_formation', 'sent_to_court',
    'documents_decision', 'waiting_hearing', 'restructuring', 'auction', 'realization', 'completed',
  ];
  const STAGE_COUNT = 8;

  function calculateProgress(currentStatus: string): number {
    const idx = STATUS_ORDER.indexOf(currentStatus);
    if (idx < 0) return 0;
    // «Завершено» — терминальный статус: все восемь этапов пройдены.
    if (currentStatus === 'completed') return 100;
    return ((idx + 0.5) / STAGE_COUNT) * 100;
  }

  it('first status → ~6.25%', () => {
    expect(calculateProgress('documents_collection')).toBeCloseTo(6.25, 1);
  });

  it('middle status → ~56.25%', () => {
    expect(calculateProgress('waiting_hearing')).toBeCloseTo(56.25, 1);
  });

  it('last stage → ~93.75%', () => {
    expect(calculateProgress('realization')).toBeCloseTo(93.75, 1);
  });

  it('completed → 100%', () => {
    expect(calculateProgress('completed')).toBe(100);
  });

  it('unknown status → 0', () => {
    expect(calculateProgress('nonexistent')).toBe(0);
  });

  it('monotonically increasing', () => {
    const values = STATUS_ORDER.map(calculateProgress);
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThan(values[i - 1]);
    }
  });
});

// ══════════════════════════════════════════════════════════
// 5. FILE SIZE FORMATTING
// ══════════════════════════════════════════════════════════

describe('formatFileSize', () => {
  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  }

  it('0 bytes', () => expect(formatFileSize(0)).toBe('0 B'));
  it('500 bytes', () => expect(formatFileSize(500)).toBe('500 B'));
  it('1 KB', () => expect(formatFileSize(1024)).toBe('1 KB'));
  it('1.5 MB', () => expect(formatFileSize(1572864)).toBe('1.5 MB'));
  it('1 GB', () => expect(formatFileSize(1073741824)).toBe('1 GB'));
});

// ══════════════════════════════════════════════════════════
// 6. INITIALS EXTRACTION
// ══════════════════════════════════════════════════════════

describe('initials from name', () => {
  function getInitials(fullName: string): string {
    return fullName.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase();
  }

  it('two words', () => expect(getInitials('Иванов Иван')).toBe('ИИ'));
  it('three words', () => expect(getInitials('Петров Пётр Петрович')).toBe('ПП'));
  it('single word', () => expect(getInitials('Сидоров')).toBe('С'));
  it('empty string', () => expect(getInitials('')).toBe(''));
  it('latin', () => expect(getInitials('John Doe')).toBe('JD'));
  it('hyphenated', () => expect(getInitials('Иванов-Петров Сергей')).toBe('ИС'));
});

// ══════════════════════════════════════════════════════════
// 7. PHONE VALIDATION
// ══════════════════════════════════════════════════════════

describe('phone normalization', () => {
  // Replicating normalizePhoneToE164 logic
  function normalizePhone(raw: string): string | null {
    const digits = raw.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('8')) return '+7' + digits.slice(1);
    if (digits.length === 10) return '+7' + digits;
    if (raw.startsWith('+') && digits.length >= 10) return '+' + digits;
    return null;
  }

  it('10 digits → +7...', () => expect(normalizePhone('9991234567')).toBe('+79991234567'));
  it('8... → +7...', () => expect(normalizePhone('89991234567')).toBe('+79991234567'));
  it('+7... passthrough', () => expect(normalizePhone('+79991234567')).toBe('+79991234567'));
  it('formatted → +7...', () => expect(normalizePhone('+7 (999) 123-45-67')).toBe('+79991234567'));
  it('too short → null', () => expect(normalizePhone('123')).toBe(null));
  it('empty → null', () => expect(normalizePhone('')).toBe(null));
  it('international', () => expect(normalizePhone('+4915112345678')).toBe('+4915112345678'));
});

// ══════════════════════════════════════════════════════════
// 8. INN VALIDATION
// ══════════════════════════════════════════════════════════

describe('INN validation', () => {
  function validateInn(inn: string, partnerType: string): string | null {
    const digits = inn.replace(/\D/g, '');
    if (partnerType === 'legal' && digits.length !== 10) return 'ИНН юрлица: 10 цифр';
    if (partnerType === 'entrepreneur' && digits.length !== 12) return 'ИНН ИП: 12 цифр';
    if (partnerType === 'individual' && digits.length !== 10 && digits.length !== 12) return 'ИНН: 10 или 12 цифр';
    return null;
  }

  it('legal 10 digits OK', () => expect(validateInn('7701234567', 'legal')).toBeNull());
  it('legal 12 digits FAIL', () => expect(validateInn('770123456789', 'legal')).not.toBeNull());
  it('entrepreneur 12 digits OK', () => expect(validateInn('770123456789', 'entrepreneur')).toBeNull());
  it('entrepreneur 10 digits FAIL', () => expect(validateInn('7701234567', 'entrepreneur')).not.toBeNull());
  it('empty string', () => expect(validateInn('', 'legal')).not.toBeNull());
});

// ══════════════════════════════════════════════════════════
// 9. SYNTH CHANGE HELPER
// ══════════════════════════════════════════════════════════

describe('syntheticChange', () => {
  function syntheticChange(name: string, value: string) {
    return { target: { name, value } } as React.ChangeEvent<HTMLInputElement>;
  }

  it('creates event with name and value', () => {
    const e = syntheticChange('email', 'test@test.com');
    expect(e.target.name).toBe('email');
    expect(e.target.value).toBe('test@test.com');
  });

  it('handles empty value', () => {
    const e = syntheticChange('phone', '');
    expect(e.target.value).toBe('');
  });
});

// ══════════════════════════════════════════════════════════
// 10. PAGES FLATTEN (infinite query)
// ══════════════════════════════════════════════════════════

describe('pages flatten', () => {
  interface Item { id: string }

  function flattenPages(pages: Item[][] | undefined): Item[] {
    return (pages ?? []).flatMap((p) => p);
  }

  it('flattens multiple pages', () => {
    const pages = [[{ id: '1' }, { id: '2' }], [{ id: '3' }]];
    expect(flattenPages(pages)).toEqual([{ id: '1' }, { id: '2' }, { id: '3' }]);
  });

  it('handles undefined', () => {
    expect(flattenPages(undefined)).toEqual([]);
  });

  it('handles empty pages', () => {
    expect(flattenPages([[], []])).toEqual([]);
  });

  it('single page', () => {
    expect(flattenPages([[{ id: '1' }]])).toEqual([{ id: '1' }]);
  });
});

// ══════════════════════════════════════════════════════════
// 11. STATUS TRANSITIONS (client-side knowledge)
// ══════════════════════════════════════════════════════════

describe('status transitions validity', () => {
  const TRANSITIONS: Record<string, string[]> = {
    documents_collection: ['documents_formation'],
    documents_formation: ['sent_to_court', 'documents_collection'],
    sent_to_court: ['documents_decision', 'documents_formation'],
    documents_decision: ['waiting_hearing', 'sent_to_court'],
    waiting_hearing: ['restructuring', 'documents_decision'],
    restructuring: ['auction', 'waiting_hearing'],
    auction: ['realization', 'restructuring'],
    realization: ['auction', 'completed'],
    completed: ['realization'],
  };

  function canTransition(from: string, to: string): boolean {
    return (TRANSITIONS[from] ?? []).includes(to);
  }

  it('documents_collection → documents_formation allowed', () => {
    expect(canTransition('documents_collection', 'documents_formation')).toBe(true);
  });

  it('documents_collection → sent_to_court NOT allowed', () => {
    expect(canTransition('documents_collection', 'sent_to_court')).toBe(false);
  });

  it('realization → auction allowed (rollback)', () => {
    expect(canTransition('realization', 'auction')).toBe(true);
  });

  it('realization → documents_collection NOT allowed', () => {
    expect(canTransition('realization', 'documents_collection')).toBe(false);
  });

  it('realization → completed allowed', () => {
    expect(canTransition('realization', 'completed')).toBe(true);
  });

  it('completed → realization allowed (reopen)', () => {
    expect(canTransition('completed', 'realization')).toBe(true);
  });

  it('completed → documents_collection NOT allowed', () => {
    expect(canTransition('completed', 'documents_collection')).toBe(false);
  });

  it('every status has at least one transition', () => {
    for (const [status, targets] of Object.entries(TRANSITIONS)) {
      expect(targets.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('all transition targets are valid statuses', () => {
    const allStatuses = new Set(Object.keys(TRANSITIONS));
    for (const targets of Object.values(TRANSITIONS)) {
      for (const t of targets) {
        expect(allStatuses.has(t)).toBe(true);
      }
    }
  });
});

// ══════════════════════════════════════════════════════════
// 12. MONEY FORMATTING
// ══════════════════════════════════════════════════════════

describe('money formatting', () => {
  function formatMoney(kopecks: number): string {
    return (kopecks / 100).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ₽';
  }

  it('1500000 kopecks → 15 000 ₽', () => {
    expect(formatMoney(1500000)).toMatch(/15[\s\u00a0]000 ₽/);
  });

  it('0 → 0 ₽', () => {
    expect(formatMoney(0)).toBe('0 ₽');
  });

  it('99 kopecks → 1 ₽ (rounded)', () => {
    expect(formatMoney(99)).toBe('1 ₽');
  });

  it('100 kopecks → 1 ₽', () => {
    expect(formatMoney(100)).toBe('1 ₽');
  });
});
