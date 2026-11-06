import apiClient from './client';

export type ChatDocumentStatus = 'unassigned' | 'assigned' | 'ignored';
export type ChatDocumentMatchedOn = 'filename' | 'text';

export interface ChatDocumentCandidate {
  client_id: string;
  full_name: string;
  status: string;
  score: number;
  matched_on: ChatDocumentMatchedOn;
}

export interface ChatDocumentAttachment {
  url: string;
  filename: string;
  size?: number | null;
  mime_type?: string | null;
}

export interface ChatDocumentAssignment {
  message_id: string;
  status: 'assigned' | 'ignored';
  client_id?: string | null;
  client_name?: string | null;
  document_type?: string | null;
  file_id?: string | null;
  assigned_at?: string | null;
  document_name?: string | null;
  duplicate?: boolean;
  bitrix_sync_status?: string | null;
  bitrix_sync_error_code?: string | null;
}

export interface ChatDocumentInboxItem {
  message_id: string;
  room_id: string;
  partner_id: string;
  partner_name?: string | null;
  sender_type: string;
  sender_label: string;
  text: string;
  created_at: string;
  attachment: ChatDocumentAttachment;
  status: ChatDocumentStatus;
  candidates: ChatDocumentCandidate[];
  assignment?: ChatDocumentAssignment | null;
}

export interface ChatDocumentInboxResponse {
  items: ChatDocumentInboxItem[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface ChatDocumentInboxFilters {
  status?: ChatDocumentStatus | 'all';
  partner_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function fetchChatDocumentInbox(
  filters: ChatDocumentInboxFilters = {},
): Promise<ChatDocumentInboxResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.partner_id) params.set('partner_id', filters.partner_id);
  if (filters.search) params.set('search', filters.search);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));

  const res = await apiClient.get<ChatDocumentInboxResponse>('/admin/chat/document-inbox', { params });
  return res.data;
}

export async function fetchChatDocumentInboxCount(): Promise<{ unassigned: number }> {
  const res = await apiClient.get<{ unassigned: number }>('/admin/chat/document-inbox/count');
  return res.data;
}

export async function fetchChatDocumentItem(messageId: string): Promise<ChatDocumentInboxItem> {
  const res = await apiClient.get<ChatDocumentInboxItem>(`/admin/chat/document-inbox/items/${messageId}`);
  return res.data;
}

export async function assignChatDocument(
  messageId: string,
  payload: { client_id: string; document_type: string; filename: string; sync_to_bitrix: boolean },
): Promise<ChatDocumentAssignment> {
  const res = await apiClient.post<ChatDocumentAssignment>(
    `/admin/chat/document-inbox/items/${messageId}/assign`,
    payload,
  );
  return res.data;
}

export async function ignoreChatDocument(messageId: string): Promise<ChatDocumentAssignment> {
  const res = await apiClient.post<ChatDocumentAssignment>(
    `/admin/chat/document-inbox/items/${messageId}/ignore`,
  );
  return res.data;
}
