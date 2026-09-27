import apiClient from './client';

export interface NotificationPreferenceData {
  user_id: string;
  email_notifications: boolean;
  new_partner_notifications: boolean;
  critical_events: boolean;
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
