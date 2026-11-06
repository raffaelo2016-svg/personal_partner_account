import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { toast } from 'sonner';
import DocumentDeleteButton, { documentDeletionErrorMessage } from './DocumentDeleteButton';
import { deleteFile, type UploadedFileResponse } from '../api/upload';

vi.mock('../api/upload', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/upload')>();
  return { ...actual, deleteFile: vi.fn() };
});

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const deleteFileMock = vi.mocked(deleteFile);

function buildFile(overrides: Partial<UploadedFileResponse> = {}): UploadedFileResponse {
  return {
    file_id: 'file-1',
    url: 'https://files.example/passport.pdf',
    filename: 'паспорт.pdf',
    size: 1024,
    mime_type: 'application/pdf',
    document_type: 'passport',
    created_at: '2026-10-29T10:00:00Z',
    bitrix_sync_status: 'synced',
    bitrix_sync_error_code: null,
    bitrix_disk_file_id: '9001',
    ...overrides,
  };
}

function renderButton(file: UploadedFileResponse): ReactElement {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = (
    <QueryClientProvider client={queryClient}>
      <DocumentDeleteButton file={file} />
    </QueryClientProvider>
  );
  render(ui);
  return ui;
}

beforeEach(() => {
  deleteFileMock.mockReset();
  vi.mocked(toast.success).mockReset();
  vi.mocked(toast.error).mockReset();
});
afterEach(cleanup);

describe('document deletion', () => {
  it('asks for confirmation and deletes the document', async () => {
    deleteFileMock.mockResolvedValue(undefined);
    renderButton(buildFile());

    fireEvent.click(screen.getByRole('button', { name: 'Удалить документ паспорт.pdf' }));
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByText(/паспорт\.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/останется в истории CRM/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Удалить' }));

    await waitFor(() => expect(deleteFileMock).toHaveBeenCalledWith('file-1'));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Документ удалён'));
  });

  it('does not offer deletion while Bitrix24 synchronization is running', () => {
    renderButton(buildFile({ bitrix_sync_status: 'processing' }));

    const button = screen.getByRole('button', { name: 'Удалить документ паспорт.pdf' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('title', 'Дождитесь завершения синхронизации с Битрикс24');
  });

  it('keeps the document and explains a rejected deletion', async () => {
    deleteFileMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { detail: { code: 'BITRIX_SYNC_IN_PROGRESS' } } },
    });
    renderButton(buildFile());

    fireEvent.click(screen.getByRole('button', { name: 'Удалить документ паспорт.pdf' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Удалить' }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(documentDeletionErrorMessage({
        isAxiosError: true,
        response: { status: 409, data: { detail: { code: 'BITRIX_SYNC_IN_PROGRESS' } } },
      })),
    );
    await waitFor(() => expect(deleteFileMock).toHaveBeenCalledTimes(1));
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('maps backend failures to human-readable messages', () => {
    expect(
      documentDeletionErrorMessage({
        isAxiosError: true,
        response: { status: 409, data: { detail: { code: 'BITRIX_SYNC_IN_PROGRESS' } } },
      }),
    ).toMatch(/синхронизируется/);
    expect(documentDeletionErrorMessage({ isAxiosError: true, response: { status: 403 } })).toMatch(/прав/);
    expect(documentDeletionErrorMessage({ isAxiosError: true, response: { status: 404 } })).toMatch(/уже удалён/);
    expect(documentDeletionErrorMessage(new Error('boom'))).toMatch(/Попробуйте ещё раз/);
  });
});
