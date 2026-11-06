import apiClient from './client';

export type AdminRole = 'admin' | 'super_admin' | 'agent';
export type InviteStatus = 'active' | 'used' | 'expired' | 'revoked';

export interface AdminUser {
  id: string;
  email: string;
  login: string | null;
  role: AdminRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  is_legacy_shared: boolean;
}

export interface Invite {
  id: string;
  email: string;
  role: AdminRole;
  status: InviteStatus;
  expires_at: string;
  created_at: string;
  created_by_label: string | null;
  invite_url?: string | null;
}

export interface InviteInfo {
  email: string;
  role: AdminRole;
  status: InviteStatus;
  expires_at: string;
  inviter_label: string | null;
}

export interface AuditEntry {
  id: string;
  created_at: string;
  actor_label: string | null;
  action: string;
  target_label: string | null;
  result: string;
  ip_address: string | null;
  user_agent: string | null;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
}

export async function getSetupStatus(): Promise<{ needs_setup: boolean }> {
  const { data } = await apiClient.get('/setup/status');
  return data;
}

export async function bootstrapSuperAdmin(payload: {
  key: string;
  email: string;
  login: string;
  password: string;
}): Promise<{ message: string }> {
  const { data } = await apiClient.post('/setup/bootstrap', payload);
  return data;
}

export async function getInviteInfo(token: string): Promise<InviteInfo> {
  const { data } = await apiClient.get(`/auth/invite/${encodeURIComponent(token)}`);
  return data;
}

export async function registerByInvite(payload: {
  token: string;
  login: string;
  password: string;
  full_name?: string;
  phone?: string;
}): Promise<{ access_token: string; user: { id: string; email: string; login?: string | null; role: AdminRole } }> {
  const { data } = await apiClient.post('/auth/invite/register', payload);
  return data;
}

export async function listAdmins(search?: string): Promise<AdminUser[]> {
  const { data } = await apiClient.get('/admin/users', { params: search ? { search } : {} });
  return data;
}

export async function updateAdmin(
  id: string,
  payload: { role?: 'admin' | 'super_admin'; is_active?: boolean },
): Promise<AdminUser> {
  const { data } = await apiClient.patch(`/admin/users/${id}`, payload);
  return data;
}

export async function resetAdminPassword(id: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/admin/users/${id}/reset-password`);
  return data;
}

export async function listInvites(): Promise<Invite[]> {
  const { data } = await apiClient.get('/admin/invites');
  return data;
}

export async function createInvite(payload: {
  email: string;
  role: AdminRole;
  ttl_hours: number;
}): Promise<Invite> {
  const { data } = await apiClient.post('/admin/invites', payload);
  return data;
}

export async function resendInvite(id: string): Promise<Invite> {
  const { data } = await apiClient.post(`/admin/invites/${id}/resend`);
  return data;
}

export async function revokeInvite(id: string): Promise<{ message: string }> {
  const { data } = await apiClient.delete(`/admin/invites/${id}`);
  return data;
}

export async function getAudit(params: {
  page?: number;
  page_size?: number;
  action?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditPage> {
  const { data } = await apiClient.get('/admin/audit', { params });
  return data;
}
