import apiClient from './client';
import type { BitrixSyncStatus } from './clients';

export interface TaskData {
  id: string;
  client_id: string | null;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  assigned_to: string;
  created_by: string;
  due_date: string | null;
  due_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  client_name?: string | null;
  partner_id?: string | null;
  partner_name?: string | null;
  bitrix_sync_status: BitrixSyncStatus;
  bitrix_sync_error_code?: string | null;
  bitrix_task_id?: string | null;
  bitrix_sync_requested_at?: string | null;
  bitrix_synced_at?: string | null;
  review_requested_at?: string | null;
  review_requested_by?: string | null;
  files_count?: number;
  messages_count?: number;
  unread_count?: number;
}

export interface TaskClientBrief {
  id: string;
  full_name: string;
  case_number: string | null;
  status: string;
  phone: string | null;
  arbitrage_court: string | null;
}

export interface TaskFileData {
  id: string;
  task_id: string;
  client_id: string | null;
  original_name: string;
  size: number;
  mime_type: string;
  created_at: string;
  uploader_id: string;
  uploader_name: string;
  can_delete: boolean;
  download_url: string;
  task_title?: string | null;
}

export interface TaskMessageData {
  id: string;
  task_id: string;
  author_id: string;
  author_name: string;
  author_role: string;
  text: string;
  created_at: string;
  is_mine: boolean;
}

export interface TaskEventData {
  id: string;
  type: string;
  actor_name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface TaskPermissions {
  is_admin: boolean;
  can_edit: boolean;
  can_upload: boolean;
  can_request_review: boolean;
  can_approve: boolean;
  can_return: boolean;
  can_delete_task: boolean;
}

export interface TaskDetailData extends TaskData {
  client: TaskClientBrief | null;
  files: TaskFileData[];
  messages: TaskMessageData[];
  events: TaskEventData[];
  permissions: TaskPermissions;
}

export type TaskReviewAction = 'request' | 'approve' | 'return';

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
  client_id?: string | null;
  partner_id?: string;
  title: string;
  description?: string;
  priority?: string;
  assigned_to?: string;
  due_date?: string | null;
  due_at?: string | null;
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  assigned_to?: string;
  due_date?: string | null;
  due_at?: string | null;
}

export interface TaskStats {
  total: number;
  pending: number;
  in_progress: number;
  review?: number;
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

export function taskFileUrl(file: TaskFileData): string {
  const base = apiClient.defaults.baseURL || '';
  if (/^https?:\/\//.test(base)) {
    return new URL(file.download_url, base).toString();
  }
  return file.download_url;
}

export async function fetchTask(id: string): Promise<TaskDetailData> {
  const res = await apiClient.get<TaskDetailData>(`/tasks/${id}`);
  return res.data;
}

export async function fetchTaskFiles(id: string): Promise<TaskFileData[]> {
  const res = await apiClient.get<TaskFileData[]>(`/tasks/${id}/files`);
  return res.data;
}

export async function uploadTaskFile(
  taskId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<TaskFileData> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiClient.post<TaskFileData>(`/tasks/${taskId}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return res.data;
}

export async function deleteTaskFile(taskId: string, fileId: string): Promise<void> {
  await apiClient.delete(`/tasks/${taskId}/files/${fileId}`);
}

export async function fetchTaskMessages(id: string): Promise<TaskMessageData[]> {
  const res = await apiClient.get<TaskMessageData[]>(`/tasks/${id}/messages`);
  return res.data;
}

export async function sendTaskMessage(id: string, text: string): Promise<TaskMessageData> {
  const res = await apiClient.post<TaskMessageData>(`/tasks/${id}/messages`, { text });
  return res.data;
}

export async function reviewTask(id: string, action: TaskReviewAction): Promise<TaskDetailData> {
  const res = await apiClient.post<TaskDetailData>(`/tasks/${id}/review`, { action });
  return res.data;
}

export async function fetchClientTaskFiles(clientId: string): Promise<TaskFileData[]> {
  const res = await apiClient.get<TaskFileData[]>(`/tasks/client-files/${clientId}`);
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
