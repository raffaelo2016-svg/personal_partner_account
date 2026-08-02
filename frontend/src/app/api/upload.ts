import apiClient from './client';
import type { BitrixSyncStatus } from './clients';

export interface UploadedFileResponse {
  file_id: string;
  url: string;
  filename: string;
  size: number;
  mime_type: string;
  document_type: string;
  created_at: string;
  bitrix_sync_status: BitrixSyncStatus;
  bitrix_sync_error_code?: string | null;
  bitrix_disk_file_id?: string | null;
}

export async function uploadFile(
  file: File,
  clientId: string,
  documentType: string = 'other',
  onProgress?: (percent: number) => void,
): Promise<UploadedFileResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await apiClient.post<UploadedFileResponse>(
    `/upload?client_id=${encodeURIComponent(clientId)}&document_type=${encodeURIComponent(documentType)}`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
    },
  );
  return res.data;
}

export async function fetchClientFiles(clientId: string): Promise<UploadedFileResponse[]> {
  const res = await apiClient.get<UploadedFileResponse[]>('/files', { params: { client_id: clientId } });
  return res.data;
}

export async function getFileUrl(fileId: string): Promise<{ file_id: string; url: string; filename: string }> {
  const res = await apiClient.get(`/files/${fileId}`);
  return res.data;
}

export async function deleteFile(fileId: string): Promise<void> {
  await apiClient.delete(`/files/${fileId}`);
}

export async function retryFileBitrix(fileId: string): Promise<UploadedFileResponse> {
  const res = await apiClient.post<UploadedFileResponse>(`/files/${fileId}/bitrix/retry`);
  return res.data;
}
