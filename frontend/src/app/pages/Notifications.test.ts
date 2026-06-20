import { describe, expect, it } from 'vitest';

describe('notification type icons', () => {
  const TYPE_ICONS: Record<string, string> = {
    new_client: '👤', status_change: '📋', payment: '💳',
    new_task: '✅', overdue: '⏰', chat: '💬', system: '🔔',
  };

  it('all types have icons', () => {
    for (const [type, icon] of Object.entries(TYPE_ICONS)) {
      expect(icon).toBeTruthy();
    }
  });

  it('unknown type → fallback', () => {
    expect(TYPE_ICONS['unknown'] ?? '📌').toBe('📌');
  });
});

describe('notification read state', () => {
  interface Notif { id: string; is_read: boolean }

  function markRead(notifs: Notif[], id: string): Notif[] {
    return notifs.map((n) => (n.id === id ? { ...n, is_read: true } : n));
  }

  it('marks specific notification', () => {
    const result = markRead([{ id: '1', is_read: false }, { id: '2', is_read: false }], '1');
    expect(result[0].is_read).toBe(true);
    expect(result[1].is_read).toBe(false);
  });

  it('immutable', () => {
    const orig = [{ id: '1', is_read: false }];
    markRead(orig, '1');
    expect(orig[0].is_read).toBe(false);
  });

  function markAllRead(notifs: Notif[]): Notif[] {
    return notifs.map((n) => ({ ...n, is_read: true }));
  }

  it('marks all read', () => {
    const result = markAllRead([{ id: '1', is_read: false }, { id: '2', is_read: false }]);
    expect(result.every((n) => n.is_read)).toBe(true);
  });

  function countUnread(notifs: Notif[]): number {
    return notifs.filter((n) => !n.is_read).length;
  }

  it('counts unread', () => expect(countUnread([{ id: '1', is_read: false }, { id: '2', is_read: true }])).toBe(1));
  it('zero unread', () => expect(countUnread([{ id: '1', is_read: true }])).toBe(0));
  it('empty', () => expect(countUnread([])).toBe(0));
});
