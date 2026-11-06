import apiClient from './client';

export async function fetchTimezone(): Promise<{ timezone: string; region?: string | null }> {
  const { data } = await apiClient.get('/settings/timezone');
  return data;
}

export async function updateTimezone(timezone: string): Promise<{ timezone: string; region?: string | null }> {
  const { data } = await apiClient.put('/settings/timezone', { timezone });
  return data;
}

export interface NotificationPreferenceData {
  user_id: string;
  email_notifications: boolean;
  new_partner_notifications: boolean;
  critical_events: boolean;
  telegram_notifications: boolean;
}

export interface TelegramConnectionData {
  available: boolean;
  connected: boolean;
  username: string | null;
  notifications_enabled: boolean;
}

export async function fetchTelegramConnection(): Promise<TelegramConnectionData> {
  const { data } = await apiClient.get('/settings/telegram');
  return data;
}

export async function createTelegramConnectLink(): Promise<{ url: string; expires_at: string }> {
  const { data } = await apiClient.post('/settings/telegram/connect');
  return data;
}

export async function disconnectTelegram(): Promise<TelegramConnectionData> {
  const { data } = await apiClient.delete('/settings/telegram');
  return data;
}

export async function fetchPartnerNotificationPreferences(): Promise<NotificationPreferenceData> {
  const { data } = await apiClient.get('/settings/notifications');
  return data;
}

export async function updatePartnerNotificationPreferences(
  prefs: Partial<NotificationPreferenceData>,
): Promise<NotificationPreferenceData> {
  const { data } = await apiClient.put('/settings/notifications', prefs);
  return data;
}

export async function changePartnerPassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await apiClient.post('/settings/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
