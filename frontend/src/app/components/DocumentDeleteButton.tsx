import { useState } from 'react';
import { isAxiosError } from 'axios';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import ConfirmDialog from './ui/ConfirmDialog';
import { deleteFile, type UploadedFileResponse } from '../api/upload';

interface Props {
  file: UploadedFileResponse;
}

interface ApiErrorDetail {
  code?: string;
  message?: string;
}

export function documentDeletionErrorMessage(error: unknown): string {
  if (isAxiosError<{ detail?: ApiErrorDetail }>(error)) {
    const status = error.response?.status;
    const code = error.response?.data?.detail?.code;
    if (status === 409 || code === 'BITRIX_SYNC_IN_PROGRESS') {
      return 'Документ ещё синхронизируется с Битрикс24. Удаление станет доступно после завершения синхронизации.';
    }
    if (status === 403) {
      return 'Недостаточно прав, чтобы удалить этот документ.';
    }
    if (status === 404) {
      return 'Документ уже удалён. Обновите страницу.';
    }
  }
  return 'Не удалось удалить документ. Попробуйте ещё раз.';
}

function isSyncInProgress(file: UploadedFileResponse) {
  return file.bitrix_sync_status === 'pending' || file.bitrix_sync_status === 'processing';
}

function dialogDescription(file: UploadedFileResponse) {
  if (file.bitrix_disk_file_id) {
    return `«${file.filename}» исчезнет из карточки клиента. Копия, уже переданная в Битрикс24, останется в истории CRM.`;
  }
  return `«${file.filename}» будет удалён из карточки клиента без возможности восстановления.`;
}

export default function DocumentDeleteButton({ file }: Props) {
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const queryClient = useQueryClient();
  const syncInProgress = isSyncInProgress(file);
  const deleteMutation = useMutation({
    mutationFn: () => deleteFile(file.file_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clientFiles'] });
      queryClient.invalidateQueries({ queryKey: ['adminClientFiles'] });
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
      toast.success('Документ удалён');
    },
    onError: (error) => toast.error(documentDeletionErrorMessage(error)),
  });

  const handleConfirm = () => {
    if (deleteMutation.isPending) return;
    deleteMutation.mutate();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setIsConfirmOpen(true)}
        disabled={syncInProgress || deleteMutation.isPending}
        title={syncInProgress ? 'Дождитесь завершения синхронизации с Битрикс24' : 'Удалить документ'}
        aria-label={`Удалить документ ${file.filename}`}
        className="p-1.5 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-gray-400 max-md:opacity-100"
      >
        {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
      </button>
      <ConfirmDialog
        open={isConfirmOpen}
        onOpenChange={setIsConfirmOpen}
        title="Удалить документ?"
        description={dialogDescription(file)}
        confirmText="Удалить"
        variant="destructive"
        onConfirm={handleConfirm}
      />
    </>
  );
}
