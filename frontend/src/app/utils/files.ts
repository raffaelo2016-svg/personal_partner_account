export const ALLOWED_FILE_FORMATS = [
  'application/zip',
  'application/x-zip-compressed',
  'image/jpeg',
  'image/jpg',
  'image/png',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

export const ALLOWED_FILE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.zip'];

export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
export const MAX_FILE_SIZE_LABEL = '10 МБ';

export interface PartitionedFiles {
  valid: File[];
  invalidFormat: string[];
  tooLarge: string[];
}

export function partitionFiles(files: FileList | File[]): PartitionedFiles {
  const valid: File[] = [];
  const invalidFormat: string[] = [];
  const tooLarge: string[] = [];
  Array.from(files).forEach((file) => {
    const ext = '.' + (file.name.split('.').pop()?.toLowerCase() ?? '');
    const formatOk = ALLOWED_FILE_FORMATS.includes(file.type) || ALLOWED_FILE_EXTENSIONS.includes(ext);
    if (!formatOk) {
      invalidFormat.push(file.name);
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      tooLarge.push(file.name);
      return;
    }
    valid.push(file);
  });
  return { valid, invalidFormat, tooLarge };
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

export interface UploadResult<T> {
  succeeded: T[];
  failed: { item: T; error: unknown }[];
}

export async function uploadAllSettled<T>(
  items: T[],
  uploader: (item: T) => Promise<unknown>,
): Promise<UploadResult<T>> {
  const results = await Promise.allSettled(items.map((item) => uploader(item)));
  const succeeded: T[] = [];
  const failed: { item: T; error: unknown }[] = [];
  results.forEach((res, idx) => {
    if (res.status === 'fulfilled') succeeded.push(items[idx]);
    else failed.push({ item: items[idx], error: res.reason });
  });
  return { succeeded, failed };
}
