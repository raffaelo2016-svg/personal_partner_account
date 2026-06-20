import { describe, expect, it } from 'vitest';

// ── getNextPageParam ────────────────────────────────────────────

describe('getNextPageParam logic', () => {
  const PAGE_SIZE = 20;

  function getNextPageParam(lastPage: { id: string }[]) {
    if (lastPage.length < PAGE_SIZE) return undefined;
    return lastPage[0]?.id;
  }

  it('returns undefined when page is smaller than PAGE_SIZE', () => {
    expect(getNextPageParam(Array.from({ length: 5 }, (_, i) => ({ id: `msg-${i}` })))).toBeUndefined();
  });

  it('returns undefined for empty page', () => {
    expect(getNextPageParam([])).toBeUndefined();
  });

  it('returns first item id as cursor when page is full', () => {
    const page = Array.from({ length: 20 }, (_, i) => ({ id: `msg-${i}` }));
    expect(getNextPageParam(page)).toBe('msg-0');
  });

  it('returns undefined when page has PAGE_SIZE - 1 items', () => {
    expect(getNextPageParam(Array.from({ length: 19 }, (_, i) => ({ id: `msg-${i}` })))).toBeUndefined();
  });

  it('returns undefined when page has exactly 1 item', () => {
    expect(getNextPageParam([{ id: 'solo' }])).toBeUndefined();
  });
});

// ── allMessages merge ───────────────────────────────────────────

describe('allMessages deduplication and sorting', () => {
  interface Msg {
    id: string;
    room_id: string;
    created_at: string;
    text: string;
    delivery_status: string;
    sender_type: string;
  }

  const mkMsg = (id: string, room: string, time: string, text = '', sender_type = 'user'): Msg => ({
    id, room_id: room, created_at: time, text, delivery_status: "sent", sender_type,
  });

  function buildAllMessages(cached: Msg[], ws: Msg[], activeRoomId: string) {
    const combined = [
      ...cached,
      ...ws.filter((wm) => wm.room_id === activeRoomId && !cached.some((m) => m.id === wm.id)),
    ];
    combined.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    return combined;
  }

  it('merges without duplicates', () => {
    const cached = [mkMsg('1', 'r1', '2026-01-01T00:00:00Z'), mkMsg('2', 'r1', '2026-01-01T00:01:00Z')];
    const ws = [mkMsg('2', 'r1', '2026-01-01T00:01:00Z'), mkMsg('3', 'r1', '2026-01-01T00:02:00Z')];
    const result = buildAllMessages(cached, ws, 'r1');
    expect(result).toHaveLength(3);
    expect(result.map((m) => m.id)).toEqual(['1', '2', '3']);
  });

  it('filters ws by activeRoomId', () => {
    const ws = [mkMsg('1', 'r1', '2026-01-01T00:00:00Z'), mkMsg('2', 'r2', '2026-01-01T00:01:00Z')];
    expect(buildAllMessages([], ws, 'r1')).toHaveLength(1);
  });

  it('sorts by created_at ASC', () => {
    const cached = [mkMsg('2', 'r1', '2026-01-01T00:02:00Z')];
    const ws = [mkMsg('1', 'r1', '2026-01-01T00:00:00Z'), mkMsg('3', 'r1', '2026-01-01T00:05:00Z')];
    expect(buildAllMessages(cached, ws, 'r1').map((m) => m.id)).toEqual(['1', '2', '3']);
  });

  it('returns empty when no messages', () => {
    expect(buildAllMessages([], [], 'r1')).toEqual([]);
  });

  it('handles cached only', () => {
    expect(buildAllMessages([mkMsg('1', 'r1', '2026-01-01T00:00:00Z')], [], 'r1')).toHaveLength(1);
  });

  it('handles ws only', () => {
    expect(buildAllMessages([], [mkMsg('1', 'r1', '2026-01-01T00:00:00Z')], 'r1')).toHaveLength(1);
  });

  it('handles many duplicates from multiple pages', () => {
    const cached = [mkMsg('1', 'r1', 'T1'), mkMsg('2', 'r1', 'T2'), mkMsg('3', 'r1', 'T3')];
    const ws = [mkMsg('1', 'r1', 'T1'), mkMsg('2', 'r1', 'T2'), mkMsg('3', 'r1', 'T3'), mkMsg('4', 'r1', 'T4')];
    expect(buildAllMessages(cached, ws, 'r1')).toHaveLength(4);
  });

  it('keeps ws messages with same timestamp but different ids', () => {
    const ws = [mkMsg('a', 'r1', '2026-01-01T00:00:00Z'), mkMsg('b', 'r1', '2026-01-01T00:00:00Z')];
    expect(buildAllMessages([], ws, 'r1')).toHaveLength(2);
  });

  it('does not include ws messages from null activeRoomId', () => {
    const ws = [mkMsg('1', 'r1', '2026-01-01T00:00:00Z')];
    expect(buildAllMessages([], ws, '')).toHaveLength(0);
  });
});

// ── WS messages_read handler ────────────────────────────────────

describe('messages_read WS handler', () => {
  interface Msg { id: string; room_id: string; delivery_status: string }

  function applyMessagesRead(messages: Msg[], roomId: string): Msg[] {
    return messages.map((m) => m.room_id === roomId ? { ...m, delivery_status: "read" } : m);
  }

  it('marks matching room messages as read', () => {
    const msgs: Msg[] = [
      { id: '1', room_id: 'r1', delivery_status: "sent" },
      { id: '2', room_id: 'r1', delivery_status: "sent" },
      { id: '3', room_id: 'r2', delivery_status: "sent" },
    ];
    const result = applyMessagesRead(msgs, 'r1');
    expect(result[0].delivery_status).toBe('read');
    expect(result[1].delivery_status).toBe('read');
    expect(result[2].delivery_status).toBe('sent');
  });

  it('does not mutate original array', () => {
    const msgs: Msg[] = [{ id: '1', room_id: 'r1', delivery_status: 'sent' }];
    applyMessagesRead(msgs, 'r1');
    expect(msgs[0].delivery_status).toBe('sent');
  });

  it('handles empty array', () => {
    expect(applyMessagesRead([], 'r1')).toEqual([]);
  });

  it('no-op when room_id does not match', () => {
    const msgs: Msg[] = [{ id: '1', room_id: 'r1', delivery_status: 'sent' }];
    const result = applyMessagesRead(msgs, 'r2');
    expect(result[0].delivery_status).toBe('sent');
  });

  it('preserves already-read messages', () => {
    const msgs: Msg[] = [{ id: '1', room_id: 'r1', delivery_status: 'read' }];
    const result = applyMessagesRead(msgs, 'r1');
    expect(result[0].delivery_status).toBe('read');
  });
});

// ── scroll trigger ──────────────────────────────────────────────

describe('scroll-to-top trigger', () => {
  function shouldLoadMore(scrollTop: number, isFetching: boolean, hasNext: boolean) {
    if (isFetching || !hasNext) return false;
    return scrollTop < 100;
  }

  it('triggers at scrollTop=0', () => expect(shouldLoadMore(0, false, true)).toBe(true));
  it('triggers at scrollTop=50', () => expect(shouldLoadMore(50, false, true)).toBe(true));
  it('triggers at scrollTop=99', () => expect(shouldLoadMore(99, false, true)).toBe(true));
  it('does not trigger at scrollTop=100', () => expect(shouldLoadMore(100, false, true)).toBe(false));
  it('does not trigger when fetching', () => expect(shouldLoadMore(0, true, true)).toBe(false));
  it('does not trigger when no next page', () => expect(shouldLoadMore(0, false, false)).toBe(false));
  it('does not trigger when fetching and no next', () => expect(shouldLoadMore(0, true, false)).toBe(false));
});

// ── WS new_message handler ──────────────────────────────────────

describe('new_message WS handler', () => {
  interface Msg { id: string; room_id: string; text: string }

  function addWsMessage(prev: Msg[], newMsg: Msg): Msg[] {
    return [...prev, newMsg];
  }

  it('appends new message', () => {
    const prev: Msg[] = [{ id: '1', room_id: 'r1', text: 'A' }];
    const result = addWsMessage(prev, { id: '2', room_id: 'r1', text: 'B' });
    expect(result).toHaveLength(2);
    expect(result[1].text).toBe('B');
  });

  it('appends from different room', () => {
    const prev: Msg[] = [];
    const result = addWsMessage(prev, { id: '1', room_id: 'r2', text: 'X' });
    expect(result).toHaveLength(1);
    expect(result[0].room_id).toBe('r2');
  });

  it('does not deduplicate (dedup is in allMessages)', () => {
    const prev: Msg[] = [{ id: '1', room_id: 'r1', text: 'A' }];
    const result = addWsMessage(prev, { id: '1', room_id: 'r1', text: 'A' });
    expect(result).toHaveLength(2); // dedup happens in allMessages, not here
  });
});

// ── intentionalClose logic ──────────────────────────────────────

describe('intentionalClose reconnect logic', () => {
  function shouldReconnect(intentionalClose: boolean) {
    return !intentionalClose;
  }

  it('reconnects on unintentional close', () => expect(shouldReconnect(false)).toBe(true));
  it('does not reconnect on intentional close', () => expect(shouldReconnect(true)).toBe(false));
});
