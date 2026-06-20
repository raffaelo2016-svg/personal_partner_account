import { describe, expect, it } from 'vitest';
import { clientFormSchema } from './client';
import { flattenZodErrors } from './registration';

describe('clientFormSchema', () => {
  it('принимает валидные данные с email', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван Иванов', email: 'ivan@example.com' });
    expect(r.success).toBe(true);
  });

  it('принимает данные без email (undefined)', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван Иванов' });
    expect(r.success).toBe(true);
  });

  it('принимает пустой email (после trim → пустая строка, refine пропускает)', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван Иванов', email: '' });
    expect(r.success).toBe(true);
  });

  it('тримит пробелы в email', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: '  ivan@example.com  ' });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.email).toBe('ivan@example.com');
  });

  it('отклоняет пустой fullName', () => {
    const r = clientFormSchema.safeParse({ fullName: '', email: 'ivan@example.com' });
    expect(r.success).toBe(false);
    expect(flattenZodErrors(r).fullName).toBe('Обязательное поле');
  });

  it('отклоняет некорректный email', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: 'not-an-email' });
    expect(r.success).toBe(false);
    expect(flattenZodErrors(r).email).toBe('Некорректный email');
  });

  it('отклоняет email с пробелом внутри', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: 'a b@c.co' });
    expect(r.success).toBe(false);
  });

  it('отклоняет email без домена', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: 'ivan@' });
    expect(r.success).toBe(false);
  });

  it('отклоняет email без локальной части', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: '@example.com' });
    expect(r.success).toBe(false);
  });

  it('отклоняет email без TLD', () => {
    const r = clientFormSchema.safeParse({ fullName: 'Иван', email: 'ivan@example' });
    expect(r.success).toBe(false);
  });
});
