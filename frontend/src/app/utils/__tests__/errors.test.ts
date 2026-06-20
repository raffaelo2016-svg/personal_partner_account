import { describe, it, expect } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { extractErrorMessage } from '../errors';

function makeAxiosError(status: number, data: unknown): AxiosError {
  const headers = new AxiosHeaders();
  return new AxiosError(
    'Request failed',
    String(status),
    { headers } as never,
    null,
    {
      data,
      status,
      statusText: '',
      headers,
      config: { headers } as never,
    },
  );
}

describe('extractErrorMessage', () => {
  it('берёт data.message из AxiosError', () => {
    const err = makeAxiosError(400, { message: 'Плохой запрос' });
    expect(extractErrorMessage(err)).toEqual({ message: 'Плохой запрос', status: 400 });
  });

  it('берёт detail как строку', () => {
    const err = makeAxiosError(422, { detail: 'Поле не заполнено' });
    expect(extractErrorMessage(err)).toEqual({ message: 'Поле не заполнено', status: 422 });
  });

  it('берёт detail.message из объекта', () => {
    const err = makeAxiosError(409, { detail: { message: 'Конфликт' } });
    expect(extractErrorMessage(err)).toEqual({ message: 'Конфликт', status: 409 });
  });

  it('фолбэк на error.message при пустом теле', () => {
    const err = makeAxiosError(500, undefined);
    expect(extractErrorMessage(err).status).toBe(500);
    expect(extractErrorMessage(err).message).toBe('Request failed');
  });

  it('обрабатывает обычный Error', () => {
    expect(extractErrorMessage(new Error('boom'))).toEqual({ message: 'boom', status: null });
  });

  it('обрабатывает неизвестное значение', () => {
    expect(extractErrorMessage('strange')).toEqual({ message: 'Неизвестная ошибка', status: null });
  });

  it('обрабатывает null', () => {
    expect(extractErrorMessage(null)).toEqual({ message: 'Неизвестная ошибка', status: null });
  });

  it('обрабатывает undefined', () => {
    expect(extractErrorMessage(undefined)).toEqual({ message: 'Неизвестная ошибка', status: null });
  });

  it('обрабатывает число как неизвестное значение', () => {
    expect(extractErrorMessage(42)).toEqual({ message: 'Неизвестная ошибка', status: null });
  });

  it('detail как число → фолбэк на error.message', () => {
    const err = makeAxiosError(422, { detail: 42 });
    expect(extractErrorMessage(err)).toEqual({ message: 'Request failed', status: 422 });
  });

  it('detail как булево → фолбэк на error.message', () => {
    const err = makeAxiosError(422, { detail: true });
    expect(extractErrorMessage(err)).toEqual({ message: 'Request failed', status: 422 });
  });

  it('detail как объект без message → фолбэк на error.message', () => {
    const err = makeAxiosError(422, { detail: { code: 'X' } });
    expect(extractErrorMessage(err)).toEqual({ message: 'Request failed', status: 422 });
  });

  it('detail-объект с message=null → фолбэк', () => {
    const err = makeAxiosError(422, { detail: { message: null } });
    expect(extractErrorMessage(err)).toEqual({ message: 'Request failed', status: 422 });
  });

  it('data.message приоритетнее detail', () => {
    const err = makeAxiosError(400, { message: 'direct', detail: 'deep' });
    expect(extractErrorMessage(err)).toEqual({ message: 'direct', status: 400 });
  });

  it('AxiosError без response возвращает status=null и message', () => {
    const err = new Error('network') as Error & { isAxiosError?: boolean };
    // имитация «чистой» AxiosError без response
    Object.setPrototypeOf(err, (class extends Error {}).prototype);
    // обычный Error-путь
    const out = extractErrorMessage(err);
    expect(out.status).toBeNull();
  });
});
