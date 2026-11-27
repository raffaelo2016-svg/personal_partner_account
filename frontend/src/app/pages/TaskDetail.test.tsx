import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TaskDetail from './TaskDetail';
import type { TaskDetailData } from '../api/tasks';

const mocks = vi.hoisted(() => ({
  task: { current: null as TaskDetailData | null },
  changeStatus: vi.fn(),
  updateTask: vi.fn(),
  reviewTask: vi.fn(),
}));

vi.mock('../hooks/useTasks', () => ({
  useTask: () => ({ data: mocks.task.current, isLoading: false, isError: false }),
  useTaskMessages: () => ({ data: [] }),
  useUpdateTask: () => ({ mutateAsync: mocks.updateTask, isPending: false }),
  useTaskReview: () => ({ mutateAsync: mocks.reviewTask, isPending: false }),
  useChangeTaskStatus: () => ({ mutateAsync: mocks.changeStatus, isPending: false }),
  useUploadTaskFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteTaskFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSendTaskMessage: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useResendTaskMessage: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const baseTask: TaskDetailData = {
  id: 'task-1',
  client_id: null,
  title: 'Проверить документы',
  description: 'Проверить пакет документов по делу.',
  status: 'pending',
  priority: 'high',
  assigned_to: 'partner',
  created_by: 'user-1',
  due_date: '2026-12-01',
  due_at: '2026-12-01T18:00:00Z',
  completed_at: null,
  created_at: '2026-11-25T09:00:00Z',
  updated_at: '2026-11-25T09:00:00Z',
  client_name: null,
  bitrix_sync_status: 'synced',
  origin: 'bitrix_gateway',
  bitrix_author_name: 'Иванова Мария',
  bitrix_client_name: 'ООО Ромашка',
  bitrix_status: 'new',
  reject_reason: null,
  status_changed_at: '2026-11-25T09:00:00Z',
  client: null,
  files: [],
  messages: [],
  events: [],
  permissions: {
    is_admin: false,
    can_edit: false,
    can_upload: true,
    can_request_review: false,
    can_approve: false,
    can_return: false,
    can_delete_task: false,
    can_change_status: true,
  },
};

function renderTask(task: TaskDetailData) {
  mocks.task.current = task;
  return render(
    <MemoryRouter initialEntries={['/dashboard/tasks/task-1']}>
      <Routes>
        <Route path="/dashboard/tasks/:id" element={<TaskDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TaskDetail: задача из Битрикса', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    mocks.changeStatus.mockReset();
    mocks.changeStatus.mockResolvedValue({ ...baseTask, status: 'rejected' });
    mocks.updateTask.mockReset();
    mocks.reviewTask.mockReset();
  });

  it('shows the partner actions and the Bitrix explanation for a gateway task', () => {
    renderTask(baseTask);

    expect(screen.getByRole('button', { name: 'Взять в работу' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Выполнено' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Отклонить' })).toBeInTheDocument();
    expect(screen.getByText(/ведётся в Битриксе/i)).toBeInTheDocument();
    expect(screen.getByText(/Автор задачи в Битриксе/i)).toBeInTheDocument();
    expect(screen.getAllByText('ООО Ромашка').length).toBeGreaterThan(0);
  });

  it('does not call the endpoint while the reject reason is empty', async () => {
    renderTask(baseTask);

    fireEvent.click(screen.getByRole('button', { name: 'Отклонить' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Отклонить задачу')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отклонить' }));

    expect(mocks.changeStatus).not.toHaveBeenCalled();
    expect(within(dialog).getByRole('alert')).toHaveTextContent(/укажите причину/i);
  });

  it('rejects with the entered reason through the partner status endpoint', async () => {
    renderTask(baseTask);

    fireEvent.click(screen.getByRole('button', { name: 'Отклонить' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/Причина отклонения/), {
      target: { value: '  Не хватает документов  ' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отклонить' }));

    await waitFor(() =>
      expect(mocks.changeStatus).toHaveBeenCalledWith({
        status: 'rejected',
        reject_reason: 'Не хватает документов',
      }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(mocks.updateTask).not.toHaveBeenCalled();
    expect(mocks.reviewTask).not.toHaveBeenCalled();
  });

  it('sends the "done" action without a reason', async () => {
    renderTask({ ...baseTask, status: 'in_progress' });

    fireEvent.click(screen.getByRole('button', { name: 'Выполнено' }));
    await waitFor(() => expect(mocks.changeStatus).toHaveBeenCalledWith({ status: 'done' }));
  });

  it('returns a completed task to work', async () => {
    renderTask({ ...baseTask, status: 'completed' });

    fireEvent.click(screen.getByRole('button', { name: 'Вернуть в работу' }));
    await waitFor(() => expect(mocks.changeStatus).toHaveBeenCalledWith({ status: 'in_progress' }));
  });

  it('returns a completed gateway task to work and shows the reopen action', () => {
    renderTask({ ...baseTask, status: 'completed' });

    expect(screen.getByRole('button', { name: 'Вернуть в работу' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Взять в работу' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Выполнено' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отклонить' })).not.toBeInTheDocument();
  });

  it('shows the rejection reason and hides internal review actions', () => {
    renderTask({
      ...baseTask,
      status: 'rejected',
      reject_reason: 'Нет документов от клиента',
      permissions: {
        ...baseTask.permissions,
        can_request_review: true,
        can_approve: true,
        can_return: true,
      },
    });

    expect(screen.getByText('Причина отклонения')).toBeInTheDocument();
    expect(screen.getByText('Нет документов от клиента')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отправить на проверку' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Завершить' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Вернуть в работу' })).toBeInTheDocument();
  });

  it('does not show partner actions without can_change_status', () => {
    renderTask({
      ...baseTask,
      permissions: { ...baseTask.permissions, can_change_status: false },
    });

    expect(screen.queryByRole('button', { name: 'Взять в работу' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Выполнено' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отклонить' })).not.toBeInTheDocument();
  });

  it('marks Bitrix status events and falls back to the Bitrix author', () => {
    renderTask({
      ...baseTask,
      status: 'rejected',
      reject_reason: 'Нет документов от клиента',
      events: [
        {
          id: 'event-1',
          type: 'status_changed',
          actor_name: null,
          payload: {
            from: 'in_progress',
            to: 'rejected',
            origin: 'bitrix_gateway',
            bitrix_author: 'Иванова Мария',
            reject_reason: 'Нет документов от клиента',
          },
          created_at: '2026-11-26T10:00:00Z',
        },
      ],
    });

    expect(screen.getAllByText('Иванова Мария').length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Статус изменён из Битрикса на «Отклонено». Причина: Нет документов от клиента/),
    ).toBeInTheDocument();
  });
});
