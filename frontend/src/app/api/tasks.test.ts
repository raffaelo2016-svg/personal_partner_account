import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('./client', () => ({
  default: {
    post: mocks.post,
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    defaults: { baseURL: '' },
  },
}));

import { changeTaskStatus } from './tasks';

describe('changeTaskStatus', () => {
  beforeEach(() => {
    mocks.post.mockReset();
    mocks.post.mockResolvedValue({ data: { id: 'task-1', status: 'rejected' } });
  });

  it('sends the partner action to POST /tasks/{id}/status with the reject reason', async () => {
    const result = await changeTaskStatus('task-1', {
      status: 'rejected',
      reject_reason: 'Не хватает документов',
    });

    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(mocks.post).toHaveBeenCalledWith('/tasks/task-1/status', {
      status: 'rejected',
      reject_reason: 'Не хватает документов',
    });
    expect(result).toMatchObject({ id: 'task-1', status: 'rejected' });
  });

  it('sends a status-only body for "in progress" and "done"', async () => {
    await changeTaskStatus('task-1', { status: 'in_progress' });
    await changeTaskStatus('task-1', { status: 'done' });

    expect(mocks.post).toHaveBeenNthCalledWith(1, '/tasks/task-1/status', { status: 'in_progress' });
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/tasks/task-1/status', { status: 'done' });
  });
});
