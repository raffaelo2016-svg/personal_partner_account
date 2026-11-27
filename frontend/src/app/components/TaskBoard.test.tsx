import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import TaskBoard from './TaskBoard';
import type { TaskData } from '../api/tasks';

const base: TaskData = {
  id: 'task-1',
  client_id: 'client-1',
  title: 'Собрать документы',
  status: 'in_progress',
  priority: 'high',
  assigned_to: 'uritech',
  created_by: 'user-1',
  due_date: null,
  due_at: null,
  created_at: '2026-11-22T10:00:00Z',
  updated_at: '2026-11-22T10:00:00Z',
  client_name: 'Смирнов Алексей',
  bitrix_sync_status: 'not_scheduled',
  origin: 'cabinet',
  files_count: 2,
  messages_count: 1,
};

describe('TaskBoard', () => {
  it('shows task in the review column and keeps counts', () => {
    render(
      <MemoryRouter>
        <TaskBoard
          tasks={[{ ...base, review_requested_at: '2026-11-22T11:00:00Z' }]}
          basePath="/dashboard/tasks"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('На проверке')).toBeInTheDocument();
    expect(screen.getByText('Собрать документы')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('renders an empty state for an empty board', () => {
    render(
      <MemoryRouter>
        <TaskBoard tasks={[]} basePath="/dashboard/tasks" />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('Новых задач нет')).toHaveLength(1);
  });

  it('renders the rejected column and keeps rejected tasks out of the overdue style', () => {
    render(
      <MemoryRouter>
        <TaskBoard
          tasks={[
            {
              ...base,
              status: 'rejected',
              assigned_to: 'partner',
              due_date: '2020-01-01',
              due_at: '2020-01-01T10:00:00Z',
              reject_reason: 'Нет документов',
            },
          ]}
          basePath="/dashboard/tasks"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Отклонено')).toBeInTheDocument();
    expect(screen.queryByText('Отклонённых задач нет')).not.toBeInTheDocument();
    expect(screen.getByText('Собрать документы')).toBeInTheDocument();
  });

  it('shows the Bitrix author and the "от ЮРИТЕХ" mark for gateway tasks', () => {
    render(
      <MemoryRouter>
        <TaskBoard
          tasks={[
            {
              ...base,
              status: 'pending',
              assigned_to: 'partner',
              origin: 'bitrix_gateway',
              bitrix_author_name: 'Иванова Мария',
              bitrix_client_name: 'ООО Ромашка',
              client_name: null,
              client_id: null,
            },
          ]}
          basePath="/dashboard/tasks"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Автор: Иванова Мария')).toBeInTheDocument();
    expect(screen.getByText('от ЮРИТЕХ')).toBeInTheDocument();
    expect(screen.getByText('ООО Ромашка')).toBeInTheDocument();
  });
});
