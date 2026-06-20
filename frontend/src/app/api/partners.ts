import apiClient from './client';
import type { Partner, PartnerCreate, PartnerUpdate } from '@/app/types';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface PartnerFilters {
  search?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface PartnerStats {
  total_partners: number;
  active_partners: number;
  total_clients: number;
  pending_partners: number;
}

export async function fetchPartners(filters: PartnerFilters = {}): Promise<PaginatedResponse<Partner>> {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.status) params.set('status', filters.status);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));

  const { data } = await apiClient.get<PaginatedResponse<Partner>>(`/admin/partners?${params}`);
  return data;
}

export async function fetchPartner(id: string): Promise<Partner> {
  const { data } = await apiClient.get<Partner>(`/admin/partners/${id}`);
  return data;
}

export async function createPartner(payload: PartnerCreate): Promise<Partner> {
  const { data } = await apiClient.post<Partner>('/admin/partners', payload);
  return data;
}

export async function updatePartner(id: string, payload: PartnerUpdate): Promise<Partner> {
  const { data } = await apiClient.put<Partner>(`/admin/partners/${id}`, payload);
  return data;
}

export async function deletePartner(id: string): Promise<void> {
  await apiClient.delete(`/admin/partners/${id}`);
}

export async function fetchPartnerStats(): Promise<PartnerStats> {
  const { data } = await apiClient.get<PartnerStats>('/admin/partners/stats');
  return data;
}
