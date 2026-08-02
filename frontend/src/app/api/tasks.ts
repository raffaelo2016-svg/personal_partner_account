import apiClient from './client';
import type { BitrixSyncStatus } from './clients';

export interface TaskData {
  id: string;
  client_id: string;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  assigned_to: string;
  created_by: string;
  due_date: string;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  client_name?: string | null;
  bitrix_sync_status: BitrixSyncStatus;
  bitrix_sync_error_code?: string | null;
  bitrix_task_id?: string | null;
  bitrix_sync_requested_at?: string | null;
  bitrix_synced_at?: string | null;
}

export interface TaskFilters {
  status?: string;
  priority?: string;
  assigned_to?: string;
  client_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface TaskCreatePayload {
  client_id: string;
  title: string;
  description?: string;
  priority?: string;
  assigned_to?: string;
  due_date: string;
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  assigned_to?: string;
  due_date?: string;
}

export interface TaskStats {
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  overdue: number;
  completion_percent: number;
}

export interface PaginatedTasks {
  items: TaskData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export async function fetchTasks(filters: TaskFilters = {}): Promise<PaginatedTasks> {
  const res = await apiClient.get<PaginatedTasks>('/tasks', { params: filters });
  return res.data;
}

export async function createTask(data: TaskCreatePayload): Promise<TaskData> {
  const res = await apiClient.post<TaskData>('/tasks', data);
  return res.data;
}

export async function updateTask(id: string, data: TaskUpdatePayload): Promise<TaskData> {
  const res = await apiClient.put<TaskData>(`/tasks/${id}`, data);
  return res.data;
}

export async function deleteTask(id: string): Promise<void> {
  await apiClient.delete(`/tasks/${id}`);
}

export async function retryTaskBitrix(id: string): Promise<TaskData> {
  const res = await apiClient.post<TaskData>(`/tasks/${id}/bitrix/retry`);
  return res.data;
}

export async function fetchTaskStats(params?: { assigned_to?: string }): Promise<TaskStats> {
  const res = await apiClient.get<TaskStats>('/tasks/stats', { params });
  return res.data;
}

export async function fetchUrgentTasks(): Promise<TaskData[]> {
  const res = await apiClient.get<TaskData[]>('/tasks/urgent');
  return res.data;
}
