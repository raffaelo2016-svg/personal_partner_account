import apiClient from './client';

export interface NewsPost {
  id: string;
  title: string;
  body: string;
  image_url: string | null;
  category: 'announcement' | 'update' | 'instruction';
  important: boolean;
  pinned: boolean;
  requires_acknowledgement: boolean;
  status: 'draft' | 'published' | 'archived';
  published_at: string | null;
  created_at: string;
  read_at: string | null;
  acknowledged_at: string | null;
}

export type NewsInput = Pick<NewsPost, 'title' | 'body' | 'category' | 'important' | 'pinned' | 'requires_acknowledgement'>;

export async function fetchNews(limit = 30): Promise<{ items: NewsPost[]; total: number }> {
  const { data } = await apiClient.get('/news', { params: { limit } });
  return data;
}

export async function fetchNewsCount(): Promise<number> {
  const { data } = await apiClient.get<{ count: number }>('/news/unread-count');
  return data.count;
}

export async function fetchNewsPost(id: string): Promise<NewsPost> {
  const { data } = await apiClient.get<NewsPost>(`/news/${id}`);
  return data;
}

export async function readNews(id: string): Promise<NewsPost> {
  const { data } = await apiClient.put<NewsPost>(`/news/${id}/read`);
  return data;
}

export async function acknowledgeNews(id: string): Promise<NewsPost> {
  const { data } = await apiClient.put<NewsPost>(`/news/${id}/acknowledge`);
  return data;
}

export async function fetchAdminNews(): Promise<{ items: NewsPost[] }> {
  const { data } = await apiClient.get('/admin/news');
  return data;
}

export async function createNews(input: NewsInput): Promise<NewsPost> {
  const { data } = await apiClient.post('/admin/news', input);
  return data;
}

export async function updateNews(id: string, input: NewsInput): Promise<NewsPost> {
  const { data } = await apiClient.patch(`/admin/news/${id}`, input);
  return data;
}

export async function uploadNewsImage(id: string, file: File): Promise<NewsPost> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post<NewsPost>(`/admin/news/${id}/image`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteNewsImage(id: string): Promise<NewsPost> {
  const { data } = await apiClient.delete<NewsPost>(`/admin/news/${id}/image`);
  return data;
}

export async function publishNews(id: string): Promise<NewsPost> {
  const { data } = await apiClient.post(`/admin/news/${id}/publish`);
  return data;
}

export async function archiveNews(id: string): Promise<NewsPost> {
  const { data } = await apiClient.post(`/admin/news/${id}/archive`);
  return data;
}

export async function fetchNewsStats(id: string): Promise<{ total: number; read: number; acknowledged: number }> {
  const { data } = await apiClient.get(`/admin/news/${id}/stats`);
  return data;
}
