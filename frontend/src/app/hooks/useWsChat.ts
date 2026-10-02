import { useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { buildWsUrl } from '../api/ws';
import { useAuthStore } from '../store/authStore';
import { captureError } from '../sentry';
import type { ChatMessageData } from '../api/chat';

const deliveryStatusSchema = z.enum(['sent', 'delivered', 'read', 'failed']);
const bitrixSyncStatusSchema = z.enum(['not_scheduled', 'pending', 'processing', 'synced', 'failed']);

const wsMessagePayloadSchema = z.object({
  id: z.string(),
  room_id: z.string(),
  sender_id: z.string().nullable().optional(),
  sender_type: z.string(),
  text: z.string(),
  delivery_status: deliveryStatusSchema.optional(),
  bitrix_sync_status: bitrixSyncStatusSchema.optional(),
  bitrix_sync_error_code: z.string().nullable().optional(),
  bitrix_message_id: z.string().nullable().optional(),
  attachment_url: z.string().nullable().optional(),
  attachment_filename: z.string().nullable().optional(),
  attachment_size: z.number().nullable().optional(),
  attachment_mime_type: z.string().nullable().optional(),
  created_at: z.string(),
});

const wsIncomingSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('new_message'), message: wsMessagePayloadSchema }),
  z.object({ type: z.literal('messages_read'), room_id: z.string() }),
  z.object({
    type: z.literal('status_update'),
    message_ids: z.array(z.string()),
    status: deliveryStatusSchema,
  }),
  z.object({ type: z.literal('typing'), room_id: z.string() }),
  z.object({ type: z.literal('message_deleted'), room_id: z.string(), message_id: z.string() }),
]);

interface UseWsChatOptions {
  roomsQueryKey: string[];
  unreadQueryKey: string[];
  messagesQueryPrefix: string;
  readerRole: 'partner' | 'admin';
  ownSenderType: string;
}

export function useWsChat(activeRoomId: string | null, options: UseWsChatOptions) {
  const [wsMessages, setWsMessages] = useState<ChatMessageData[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [typingUsers, setTypingUsers] = useState<Record<string, number>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();
  const reconnectDelay = useRef(1000);
  const intentionalClose = useRef(false);
  const activeRoomIdRef = useRef<string | null>(null);
  const typingTimeout = useRef<ReturnType<typeof setTimeout>>();

  // Store options in refs to avoid re-creating connectWs
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  useEffect(() => {
    activeRoomIdRef.current = activeRoomId;
  }, [activeRoomId]);

  const connectWs = useCallback(() => {
    const currentToken = tokenRef.current;
    if (!currentToken) return;
    intentionalClose.current = false;
    const ws = new WebSocket(buildWsUrl('/ws/chat'));

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token: currentToken }));
      setWsConnected(true);
      reconnectDelay.current = 1000;
    };

    ws.onmessage = (event) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        return;
      }
      const result = wsIncomingSchema.safeParse(parsed);
      if (!result.success) {
        captureError(result.error, { context: 'ws_chat_message', payload: parsed });
        return;
      }
      const data = result.data;
      const opts = optionsRef.current;

      if (data.type === 'new_message') {
        const msg: ChatMessageData = {
          id: data.message.id,
          room_id: data.message.room_id,
          sender_id: data.message.sender_id ?? null,
          sender_type: data.message.sender_type,
          text: data.message.text,
          delivery_status: data.message.delivery_status ?? 'sent',
          bitrix_sync_status: data.message.bitrix_sync_status ?? 'not_scheduled',
          bitrix_sync_error_code: data.message.bitrix_sync_error_code,
          bitrix_message_id: data.message.bitrix_message_id,
          attachment_url: data.message.attachment_url,
          attachment_filename: data.message.attachment_filename,
          attachment_size: data.message.attachment_size,
          attachment_mime_type: data.message.attachment_mime_type,
          created_at: data.message.created_at,
        };
        setWsMessages((prev) => [...prev, msg]);
        ws.send(JSON.stringify({ type: 'delivered', message_ids: [msg.id] }));
        if (msg.room_id === activeRoomIdRef.current && msg.sender_type !== opts.ownSenderType) {
          ws.send(JSON.stringify({ type: 'read', room_id: msg.room_id, reader_role: opts.readerRole }));
          // Дать бэку обработать read, потом обновить rooms (unread=0)
          setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: opts.roomsQueryKey });
            queryClient.invalidateQueries({ queryKey: opts.unreadQueryKey });
          }, 300);
        } else {
          queryClient.invalidateQueries({ queryKey: opts.roomsQueryKey });
          queryClient.invalidateQueries({ queryKey: opts.unreadQueryKey });
        }
      } else if (data.type === 'messages_read') {
        setWsMessages((prev) =>
          prev.map((m) => (m.room_id === data.room_id ? { ...m, delivery_status: 'read' } : m)),
        );
      } else if (data.type === 'status_update') {
        const ids = new Set(data.message_ids);
        setWsMessages((prev) =>
          prev.map((m) => (ids.has(m.id) ? { ...m, delivery_status: data.status } : m)),
        );
      } else if (data.type === 'typing') {
        const roomId = data.room_id;
        setTypingUsers((prev) => ({ ...prev, [roomId]: Date.now() }));
        setTimeout(() => {
          setTypingUsers((prev) => {
            const t = prev[roomId];
            if (t && Date.now() - t >= 2000) {
              const { [roomId]: _, ...rest } = prev;
              return rest;
            }
            return prev;
          });
        }, 2500);
      } else if (data.type === 'message_deleted') {
        setWsMessages((prev) => prev.filter((m) => m.id !== data.message_id));
        queryClient.invalidateQueries({ queryKey: [opts.messagesQueryPrefix] });
        queryClient.invalidateQueries({ queryKey: opts.roomsQueryKey });
        queryClient.invalidateQueries({ queryKey: opts.unreadQueryKey });
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      if (!intentionalClose.current) {
        reconnectTimeout.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
          connectWs();
        }, reconnectDelay.current);
      }
    };

    ws.onerror = (event) => {
      captureError(new Error('WebSocket error'), { event: String(event.type) });
      ws.close();
    };
    wsRef.current = ws;
  }, [queryClient]); // only queryClient — stable singleton

  useEffect(() => {
    connectWs();
    return () => {
      intentionalClose.current = true;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connectWs]);

  // Если токен появился позже монтирования (login без перезагрузки) — переподключиться.
  useEffect(() => {
    if (token && !wsConnected && !wsRef.current) {
      intentionalClose.current = false;
      connectWs();
    }
  }, [token, wsConnected, connectWs]);

  // При открытии комнаты отметить старые сообщения как прочитанные.
  // Без этого unread_count остаётся, если на входе не приходило новых сообщений в эту комнату.
  useEffect(() => {
    if (!activeRoomId || !wsConnected || !wsRef.current) return;
    const opts = optionsRef.current;
    wsRef.current.send(
      JSON.stringify({ type: 'read', room_id: activeRoomId, reader_role: opts.readerRole }),
    );
    const t = setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: opts.roomsQueryKey });
      queryClient.invalidateQueries({ queryKey: opts.unreadQueryKey });
    }, 300);
    return () => clearTimeout(t);
  }, [activeRoomId, wsConnected, queryClient]);

  const sendTyping = useCallback(() => {
    if (!wsRef.current || !activeRoomId) return;
    if (typingTimeout.current) return;
    wsRef.current.send(JSON.stringify({ type: 'typing', room_id: activeRoomId }));
    typingTimeout.current = setTimeout(() => {
      typingTimeout.current = undefined;
    }, 2000);
  }, [activeRoomId]);

  const clearWsMessages = useCallback(() => {
    setWsMessages([]);
  }, []);

  return { wsMessages, wsConnected, typingUsers, sendTyping, clearWsMessages };
}
