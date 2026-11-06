import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { TaskData } from '../api/tasks';
import AdminTasks from './AdminTasks';
import TasksList from './TasksList';

const mocks = vi.hoisted(() => ({
  create: vi.fn(), update: vi.fn(), task: null as TaskData | null,
}));

vi.mock('../hooks/useTasks', () => ({
  useInfiniteTasks: () => ({
    data: { pages: [{ items: mocks.task ? [mocks.task] : [] }] },
    isLoading: false, hasNextPage: false, isFetchingNextPage: false, fetchNextPage: vi.fn(),
  }),
  useTaskStats: () => ({ data: { total: 1 } }),
  useCreateTask: () => ({ mutate: mocks.create, isPending: false }),
  useUpdateTask: () => ({ mutate: mocks.update, isPending: false }),
  useDeleteTask: () => ({ mutate: vi.fn(), isPending: false }),
  useRetryTaskBitrix: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('../hooks/usePartners', () => ({
  usePartners: () => ({ data: { items: [{ id: 'partner-1', company_name: 'Партнёр', director_name: 'Иван' }] } }),
}));
vi.mock('../hooks/useClients', () => ({ useClients: () => ({ data: { items: [] } }) }));
vi.mock('../hooks/useIntersectionObserver', () => ({ useIntersectionObserver: () => null }));
vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({ data: { items: [] } }) }));
vi.mock('../components/BitrixSyncStatus', () => ({ default: () => null }));
vi.mock('../components/ui/ConfirmDialog', () => ({ default: () => null }));
vi.mock('../components/ui/CustomSelect', () => ({
  default: ({ value, onChange, options, placeholder }: {
    value: string; onChange: (value: string) => void;
    options: { value: string; label: string; disabled?: boolean }[]; placeholder?: string;
  }) => (
    <select aria-label={placeholder ?? 'Выбор'} value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
    </select>
  ),
}));

function task(overrides: Partial<TaskData> = {}): TaskData {
  return {
    id: 'task-1', client_id: null, title: 'Проверить документы', status: 'pending',
    priority: 'medium', assigned_to: 'partner', created_by: 'admin-1',
    due_date: null, due_at: null, bitrix_sync_status: 'synced',
    created_at: '2026-10-15T10:00:00Z', updated_at: '2026-10-15T10:00:00Z',
    ...overrides,
  };
}

function renderAdmin() {
  render(<MemoryRouter initialEntries={['/tasks?direction=my']}><AdminTasks /></MemoryRouter>);
}

beforeEach(() => { vi.clearAllMocks(); mocks.task = null; });
afterEach(cleanup);

describe('task deadline forms', () => {
  it('creates a task directly for a partner without a client or deadline', () => {
    renderAdmin();
    fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }));
    fireEvent.change(screen.getByPlaceholderText('Введите название задачи'), { target: { value: 'Общая задача' } });
    fireEvent.change(screen.getByLabelText('Выберите партнёра'), { target: { value: 'partner-1' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Создать задачу' }).slice(-1)[0]);
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      partner_id: 'partner-1', client_id: undefined, due_date: null, due_at: null, assigned_to: 'partner',
    }), expect.anything());
  });

  it('sends the chosen Moscow date and time as an exact UTC deadline', () => {
    renderAdmin();
    fireEvent.click(screen.getByRole('button', { name: 'Создать задачу' }));
    fireEvent.change(screen.getByPlaceholderText('Введите название задачи'), { target: { value: 'Документы' } });
    fireEvent.change(screen.getByLabelText('Выберите партнёра'), { target: { value: 'partner-1' } });
    fireEvent.change(screen.getByLabelText('Дата срока (МСК)'), { target: { value: '2026-10-15' } });
    fireEvent.change(screen.getByLabelText('Время срока (МСК)'), { target: { value: '12:30' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Создать задачу' }).slice(-1)[0]);
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      due_date: '2026-10-15', due_at: '2026-10-15T09:30:00.000Z',
    }), expect.anything());
  });

  it.each([
    { due_date: '2026-10-15', due_at: null },
    { due_date: '2026-10-15', due_at: '2026-10-15T09:30:45Z' },
  ])('preserves an existing deadline when editing other fields: %j', (deadline) => {
    mocks.task = task(deadline);
    renderAdmin();
    fireEvent.click(screen.getByTitle('Редактировать задачу'));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    const payload = mocks.update.mock.calls[0][0].data;
    expect(payload).not.toHaveProperty('due_date');
    expect(payload).not.toHaveProperty('due_at');
  });

  it('clears both deadline fields explicitly', () => {
    mocks.task = task({ due_date: '2026-10-15', due_at: '2026-10-15T09:30:00Z' });
    renderAdmin();
    fireEvent.click(screen.getByTitle('Редактировать задачу'));
    fireEvent.click(screen.getByRole('button', { name: 'Убрать срок' }));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    expect(mocks.update).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({ due_date: null, due_at: null }),
    }), expect.anything());
  });

  it('shows a received general task without a deadline or content-edit actions', () => {
    mocks.task = task();
    render(<MemoryRouter><TasksList /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Задачи от ЮРИТЕХ' }));
    expect(screen.getByText('Общая задача')).toBeInTheDocument();
    expect(screen.getByText('Без срока')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Редактировать задачу')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Удалить задачу')).not.toBeInTheDocument();
  });
});
