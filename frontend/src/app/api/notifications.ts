import apiClient from './client';

export interface NotificationData {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  link?: string | null;
  created_at: string;
}

export interface PaginatedNotifications {
  items: NotificationData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export async function fetchNotifications(params: { is_read?: boolean; page?: number } = {}): Promise<PaginatedNotifications> {
  const res = await apiClient.get<PaginatedNotifications>('/notifications', { params });
  return res.data;
}

export async function fetchUnreadCount(): Promise<number> {
  const res = await apiClient.get<{ count: number }>('/notifications/unread-count');
  return res.data.count;
}

export async function markNotificationRead(id: string): Promise<NotificationData> {
  const res = await apiClient.put<NotificationData>(`/notifications/${id}/read`);
  return res.data;
}

export async function markAllNotificationsRead(): Promise<{ marked_read: number }> {
  const res = await apiClient.put<{ marked_read: number }>('/notifications/read-all');
  return res.data;
}
