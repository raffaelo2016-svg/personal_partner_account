import apiClient from './client';
import type { BitrixSyncStatus } from './clients';

export type AttentionEntityType = 'all' | 'partner' | 'client' | 'file' | 'task';
export type AttentionSyncStatus = 'all' | 'failed' | 'conflict' | 'pending' | 'not_scheduled';

export interface BitrixAttentionItem {
  entity_type: Exclude<AttentionEntityType, 'all'>;
  entity_id: string;
  parent_id?: string | null;
  sync_status: BitrixSyncStatus;
  error_code: string;
  occurred_at: string;
}

export interface BitrixAttentionResponse {
  items: BitrixAttentionItem[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
  counts: Record<Exclude<AttentionEntityType, 'all'>, number>;
}

export async function fetchBitrixAttention(params: {
  entity_type?: AttentionEntityType;
  sync_status?: AttentionSyncStatus;
  page?: number;
  page_size?: number;
} = {}): Promise<BitrixAttentionResponse> {
  const { data } = await apiClient.get<BitrixAttentionResponse>('/admin/bitrix-attention', { params });
  return data;
}
