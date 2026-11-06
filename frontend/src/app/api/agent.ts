import apiClient from './client';

export interface AgentProfile {
  id: string;
  code: string;
  full_name: string;
  phone: string;
  company_name: string | null;
  status: string;
  requisites_status: string;
  requisites_recipient_type: string;
  referral_link: string;
}

export interface AgentStats {
  partners: number;
  clients: number;
  accrued: number;
  reserved: number;
  paid: number;
  available: number;
}

export interface AgentMe {
  profile: AgentProfile;
  stats: AgentStats;
}

export interface AgentPartner {
  id: string;
  name: string;
  status: string;
  linked_at: string | null;
  clients: number;
  accrued: number;
}

export interface AgentAccrual {
  id: string;
  client_ref: string;
  partner_name: string;
  created_at: string;
  amount: number;
  rate: number;
  status: string;
  reason: string;
}

export interface AgentPayout {
  id: string;
  amount: number;
  status: string;
  period: string;
  created_at: string;
  paid_at: string | null;
  comment: string | null;
}

export async function getAgentMe(): Promise<AgentMe> {
  const { data } = await apiClient.get('/agent/me');
  return data;
}

export async function getAgentPartners(): Promise<AgentPartner[]> {
  const { data } = await apiClient.get('/agent/partners');
  return data;
}

export async function getAgentAccruals(): Promise<AgentAccrual[]> {
  const { data } = await apiClient.get('/agent/accruals');
  return data;
}

export async function getAgentPayouts(): Promise<AgentPayout[]> {
  const { data } = await apiClient.get('/agent/payouts');
  return data;
}

export async function requestPayout(): Promise<AgentPayout> {
  const { data } = await apiClient.post('/agent/payouts');
  return data;
}

export async function saveRequisites(payload: {
  recipient_type: string;
  data: Record<string, string>;
}): Promise<AgentProfile> {
  const { data } = await apiClient.put('/agent/requisites', payload);
  return data;
}

export async function registerAgent(payload: {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  company_name?: string;
}): Promise<{ access_token: string; user: { id: string; email: string; role: string } }> {
  const { data } = await apiClient.post('/auth/register-agent', payload);
  return data;
}

// ---------------------------------------------------------------- админка

export interface AdminAgent {
  id: string;
  email: string;
  code: string;
  full_name: string;
  company_name: string | null;
  status: string;
  created_at: string;
  requisites_status: string;
  stats: AgentStats;
}

export interface AdminAgentDetail {
  agent: AdminAgent;
  partners: AgentPartner[];
  accruals: AgentAccrual[];
  payouts: AgentPayout[];
}

export async function listAgents(search?: string): Promise<AdminAgent[]> {
  const { data } = await apiClient.get('/admin/agents', { params: search ? { search } : {} });
  return data;
}

export async function getAgentDetail(id: string): Promise<AdminAgentDetail> {
  const { data } = await apiClient.get(`/admin/agents/${id}`);
  return data;
}

export async function setAgentStatus(id: string, isActive: boolean, reason?: string): Promise<AdminAgent> {
  const { data } = await apiClient.patch(`/admin/agents/${id}`, { is_active: isActive, reason });
  return data;
}

export async function reviewAgentRequisites(
  id: string,
  status: 'accepted' | 'needs_fix',
  comment?: string,
): Promise<AdminAgent> {
  const { data } = await apiClient.patch(`/admin/agents/${id}/requisites`, { status, comment });
  return data;
}

export async function listAllPayouts(status?: string): Promise<AgentPayout[]> {
  const { data } = await apiClient.get('/admin/payouts', { params: status ? { status } : {} });
  return data;
}

export async function updatePayoutStatus(
  id: string,
  status: string,
  comment?: string,
): Promise<AgentPayout> {
  const { data } = await apiClient.patch(`/admin/payouts/${id}`, { status, comment });
  return data;
}
