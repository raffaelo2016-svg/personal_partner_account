import apiClient from './client';

export type DocumentPreparationMode = 'uritech' | 'partner';
export type GeneratedDocumentKind = 'application' | 'creditors' | 'inventory';
export type DocumentGenerationData = Record<string, unknown>;

export interface ClientFilters {
  search?: string;
  type?: string;
  status?: string;
  category?: string;
  partner_id?: string;
  page?: number;
  page_size?: number;
}

export interface ClientData {
  id: string;
  partner_id: string;
  partner_name?: string | null;
  type: string;
  document_preparation_mode: DocumentPreparationMode;
  document_generation_data: DocumentGenerationData;
  status: string;
  full_name: string;
  date_of_birth?: string | null;
  passport_series?: string | null;
  passport_number?: string | null;
  passport_issue_date?: string | null;
  passport_issued_by?: string | null;
  registration_address?: string | null;
  inn?: string | null;
  snils?: string | null;
  phone?: string | null;
  email?: string | null;
  region?: string | null;
  arbitrage_court?: string | null;
  case_number?: string | null;
  court_procedure_date?: string | null;
  court_fee_per_client?: number | null;
  bitrix_sync_status: BitrixSyncStatus;
  bitrix_sync_error_code?: string | null;
  bitrix_contact_id?: string | null;
  bitrix_deal_id?: string | null;
  bitrix_sync_requested_at?: string | null;
  bitrix_synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type BitrixSyncStatus = 'not_scheduled' | 'pending' | 'processing' | 'synced' | 'failed' | 'conflict';

export interface ClientStats {
  total: number;
  before_court: number;
  in_court: number;
  completed: number;
  new_this_week: number;
}

export interface PaginatedClients {
  items: ClientData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface ClientCreatePayload {
  type: string;
  document_preparation_mode?: DocumentPreparationMode;
  document_generation_data?: DocumentGenerationData;
  full_name: string;
  date_of_birth?: string | null;
  passport_series?: string | null;
  passport_number?: string | null;
  passport_issue_date?: string | null;
  passport_issued_by?: string | null;
  registration_address?: string | null;
  inn?: string | null;
  snils?: string | null;
  phone?: string | null;
  email?: string | null;
  region?: string | null;
  arbitrage_court?: string | null;
  case_number?: string | null;
}

export interface ClientUpdatePayload {
  type?: string;
  document_preparation_mode?: DocumentPreparationMode;
  document_generation_data?: DocumentGenerationData;
  status?: string;
  full_name?: string;
  date_of_birth?: string | null;
  passport_series?: string | null;
  passport_number?: string | null;
  passport_issue_date?: string | null;
  passport_issued_by?: string | null;
  registration_address?: string | null;
  inn?: string | null;
  snils?: string | null;
  phone?: string | null;
  email?: string | null;
  region?: string | null;
  arbitrage_court?: string | null;
  case_number?: string | null;
  court_procedure_date?: string | null;
}

export async function fetchClients(filters: ClientFilters = {}): Promise<PaginatedClients> {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.type) params.set('type', filters.type);
  if (filters.status) params.set('status', filters.status);
  if (filters.category) params.set('category', filters.category);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));

  const res = await apiClient.get<PaginatedClients>('/clients', { params });
  return res.data;
}

export async function fetchClient(id: string): Promise<ClientData> {
  const res = await apiClient.get<ClientData>(`/clients/${id}`);
  return res.data;
}

export async function createClient(data: ClientCreatePayload): Promise<ClientData> {
  const res = await apiClient.post<ClientData>('/clients', data);
  return res.data;
}

export async function updateClient(id: string, data: ClientUpdatePayload): Promise<ClientData> {
  const res = await apiClient.put<ClientData>(`/clients/${id}`, data);
  return res.data;
}

export async function deleteClient(id: string): Promise<void> {
  await apiClient.delete(`/clients/${id}`);
}

export async function downloadGeneratedDocument(
  id: string,
  kind: GeneratedDocumentKind,
  options: { admin?: boolean } = {},
): Promise<void> {
  const names: Record<GeneratedDocumentKind, string> = {
    application: 'Заявление в суд.docx',
    creditors: 'Список кредиторов и должников.docx',
    inventory: 'Опись имущества.docx',
  };
  const endpoint = options.admin
    ? `/admin/clients/${id}/documents/${kind}`
    : `/clients/${id}/documents/${kind}`;
  const response = options.admin
    ? await apiClient.post<Blob>(endpoint, undefined, { responseType: 'blob' })
    : await apiClient.get<Blob>(endpoint, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = names[kind];
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function fetchClientStats(): Promise<ClientStats> {
  const res = await apiClient.get<ClientStats>('/clients/stats');
  return res.data;
}

export async function fetchAdminClients(filters: ClientFilters = {}): Promise<PaginatedClients> {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.type) params.set('type', filters.type);
  if (filters.status) params.set('status', filters.status);
  if (filters.partner_id) params.set('partner_id', filters.partner_id);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));

  const res = await apiClient.get<PaginatedClients>('/admin/clients', { params });
  return res.data;
}

export async function fetchAdminClient(id: string): Promise<ClientData> {
  const res = await apiClient.get<ClientData>(`/admin/clients/${id}`);
  return res.data;
}

export async function updateAdminClient(id: string, data: ClientUpdatePayload): Promise<ClientData> {
  const res = await apiClient.put<ClientData>(`/admin/clients/${id}`, data);
  return res.data;
}

export async function retryAdminClientBitrix(id: string): Promise<ClientData> {
  const res = await apiClient.post<ClientData>(`/admin/clients/${id}/bitrix/retry`);
  return res.data;
}

export interface ProgressSubStep {
  title: string;
  status: string;
  completed_at?: string | null;
}

export interface ProgressStage {
  id: number;
  title: string;
  status: string;
  sub_steps: ProgressSubStep[];
}

export interface ClientProgress {
  overall_percent: number;
  current_status: string;
  stages: ProgressStage[];
}

export async function fetchClientProgress(clientId: string): Promise<ClientProgress> {
  const res = await apiClient.get<ClientProgress>(`/clients/${clientId}/progress`);
  return res.data;
}

export async function changeClientStatus(
  clientId: string,
  status: string,
  comment?: string,
): Promise<ClientData> {
  const res = await apiClient.post<ClientData>(`/clients/${clientId}/status`, { status, comment });
  return res.data;
}

export interface StatusLogEntry {
  id: number;
  client_id: string;
  from_status: string;
  to_status: string;
  changed_by: string;
  comment?: string | null;
  changed_at: string;
}

export async function fetchStatusHistory(clientId: string): Promise<StatusLogEntry[]> {
  const res = await apiClient.get<StatusLogEntry[]>(`/clients/${clientId}/status-history`);
  return res.data;
}
