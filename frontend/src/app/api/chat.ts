import apiClient from './client';

export interface ChatRoomData {
  id: string;
  partner_id: string;
  type: string;
  created_at: string;
  last_message?: string | null;
  unread_count: number;
  partner_name?: string | null;
}

export interface ChatMessageData {
  id: string;
  room_id: string;
  sender_id?: string | null;
  sender_type: string;
  text: string;
  delivery_status: 'sent' | 'delivered' | 'read' | 'failed';
  bitrix_sync_status: 'not_scheduled' | 'pending' | 'processing' | 'synced' | 'failed';
  bitrix_sync_error_code?: string | null;
  bitrix_message_id?: string | null;
  attachment_url?: string | null;
  attachment_filename?: string | null;
  attachment_size?: number | null;
  attachment_mime_type?: string | null;
  created_at: string;
}

export interface ChatMessageEventData {
  id: string;
  room_id: string;
  chat_message_id?: string | null;
  bitrix_message_id: string;
  event_type: 'updated' | 'deleted';
  actor_id?: string | null;
  event_at: string;
  created_at: string;
}

export async function fetchChatRooms(): Promise<ChatRoomData[]> {
  const res = await apiClient.get<ChatRoomData[]>('/chat/rooms');
  return res.data;
}

export async function fetchChatMessages(
  roomId: string,
  params: { limit?: number; before?: string } = {},
): Promise<ChatMessageData[]> {
  const res = await apiClient.get<ChatMessageData[]>(`/chat/rooms/${roomId}/messages`, { params });
  return res.data;
}

export async function sendChatMessage(roomId: string, text: string): Promise<ChatMessageData> {
  const res = await apiClient.post<ChatMessageData>(`/chat/rooms/${roomId}/messages`, { text });
  return res.data;
}

export async function sendChatAttachment(roomId: string, text: string, file: File): Promise<ChatMessageData> {
  const formData = new FormData();
  formData.append('text', text);
  formData.append('file', file);
  const res = await apiClient.post<ChatMessageData>(`/chat/rooms/${roomId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function fetchPartnerUnreadCount(): Promise<number> {
  const res = await apiClient.get<{ unread_count: number }>('/chat/unread-count');
  return res.data.unread_count;
}

export async function fetchAdminChatRooms(search?: string, roomType: 'admin' | 'tech_support' = 'admin'): Promise<ChatRoomData[]> {
  const res = await apiClient.get<ChatRoomData[]>('/admin/chat/rooms', { params: { ...(search ? { search } : {}), room_type: roomType } });
  return res.data;
}

export async function fetchAdminChatMessages(
  roomId: string,
  params: { limit?: number; before?: string } = {},
): Promise<ChatMessageData[]> {
  const res = await apiClient.get<ChatMessageData[]>(`/admin/chat/rooms/${roomId}/messages`, { params });
  return res.data;
}

export async function fetchAdminChatMessageEvents(roomId: string): Promise<ChatMessageEventData[]> {
  const res = await apiClient.get<ChatMessageEventData[]>(`/admin/chat/rooms/${roomId}/events`);
  return res.data;
}

export async function sendAdminChatMessage(roomId: string, text: string): Promise<ChatMessageData> {
  const res = await apiClient.post<ChatMessageData>(`/admin/chat/rooms/${roomId}/messages`, { text });
  return res.data;
}

export async function sendAdminChatAttachment(roomId: string, text: string, file: File): Promise<ChatMessageData> {
  const formData = new FormData();
  formData.append('text', text);
  formData.append('file', file);
  const res = await apiClient.post<ChatMessageData>(`/admin/chat/rooms/${roomId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function fetchAdminUnreadCount(): Promise<number> {
  const res = await apiClient.get<{ unread_count: number }>('/admin/chat/unread-count');
  return res.data.unread_count;
}
