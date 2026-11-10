import { AxiosError } from 'axios';

const CODE_MESSAGES: Record<string, string> = {
  INVITE_INVALID: 'Ссылка недействительна',
  INVITE_USED: 'Ссылка уже использована',
  INVITE_REVOKED: 'Приглашение отозвано',
  INVITE_EXPIRED: 'Срок действия ссылки истёк',
  EMAIL_TAKEN: 'Эта почта уже используется',
  LOGIN_TAKEN: 'Этот логин уже занят',
  WEAK_PASSWORD: 'Пароль слишком простой',
  INVALID_LOGIN: 'Некорректный логин',
  LAST_SUPER_ADMIN: 'В системе должен остаться хотя бы один супер-администратор',
  SELF_ACTION_FORBIDDEN: 'Нельзя выполнить это действие над собой',
  BOOTSTRAP_KEY_INVALID: 'Ключ недействителен или истёк',
  SETUP_ALREADY_DONE: 'Система уже настроена',
  RATE_LIMITED: 'Слишком много попыток. Попробуйте позже',
};

interface ApiDetail {
  code?: string;
  message?: string;
  detail?: string;
}

export function getApiErrorMessage(error: unknown, fallback = 'Что-то пошло не так. Попробуйте ещё раз'): string {
  const axiosError = error as AxiosError<ApiDetail | { detail?: ApiDetail }>;

  const payload = axiosError?.response?.data;
  if (payload && typeof payload === 'object') {
    const direct = payload as ApiDetail;
    if (direct?.code && CODE_MESSAGES[direct.code]) return CODE_MESSAGES[direct.code];
    if (typeof direct?.message === 'string' && direct.message) return direct.message;

    const nested = (payload as { detail?: ApiDetail }).detail;
    if (nested && typeof nested === 'object') {
      if (nested.code && CODE_MESSAGES[nested.code]) return CODE_MESSAGES[nested.code];
      if (typeof nested.message === 'string' && nested.message) return nested.message;
    }
    if (typeof nested === 'string' && nested) return nested;
  }

  const headerCode = axiosError?.response?.headers?.code as string | undefined;
  if (headerCode && CODE_MESSAGES[headerCode]) return CODE_MESSAGES[headerCode];

  return fallback;
}
