import apiClient from './client';

export interface SystemSettingData {
  key: string;
  value: string;
  updated_at: string | null;
}

export interface NotificationPreferenceData {
  user_id: string;
  email_notifications: boolean;
  new_partner_notifications: boolean;
  critical_events: boolean;
}

export interface LoginHistoryEntry {
  id: string;
  user_id: string;
  ip_address: string | null;
  user_agent: string | null;
  logged_at: string;
}

export async function fetchSystemSettings(): Promise<SystemSettingData[]> {
  const { data } = await apiClient.get('/admin/settings');
  return data;
}

export async function updateSystemSettings(
  settings: Record<string, string>,
): Promise<SystemSettingData[]> {
  const { data } = await apiClient.put('/admin/settings', { settings });
  return data;
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferenceData> {
  const { data } = await apiClient.get('/admin/settings/notifications');
  return data;
}

export async function updateNotificationPreferences(
  prefs: Partial<NotificationPreferenceData>,
): Promise<NotificationPreferenceData> {
  const { data } = await apiClient.put('/admin/settings/notifications', prefs);
  return data;
}

export async function changeAdminPassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await apiClient.post('/admin/settings/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function fetchLoginHistory(): Promise<LoginHistoryEntry[]> {
  const { data } = await apiClient.get('/admin/settings/login-history');
  return data;
}

export async function triggerBackup(): Promise<{ detail: string; status: string }> {
  const { data } = await apiClient.post('/admin/settings/backup');
  return data;
}
