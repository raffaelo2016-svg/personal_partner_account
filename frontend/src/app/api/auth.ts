import apiClient from './client';

export interface LoginPayload {
  /** Почта или логин — бэкенд принимает оба варианта. */
  identifier: string;
  password: string;
  captcha_token?: string;
}

export interface AuthUserResponse {
  id: string;
  email: string;
  role: 'partner' | 'admin' | 'super_admin' | 'agent';
  login?: string | null;
  company_name?: string | null;
}

export interface TokenResponse {
  access_token: string;
  user: AuthUserResponse;
}

export interface RefreshResponse {
  access_token: string;
}

export async function loginApi(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload);
  return data;
}

export async function refreshApi(): Promise<RefreshResponse> {
  const { data } = await apiClient.post<RefreshResponse>('/auth/refresh', {});
  return data;
}

export async function logoutApi(): Promise<void> {
  await apiClient.post('/auth/logout', {});
}

export async function getMeApi(): Promise<AuthUserResponse> {
  const { data } = await apiClient.get<AuthUserResponse>('/auth/me');
  return data;
}

export async function forgotPasswordApi(email: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>('/auth/forgot-password', { email });
  return data;
}

export async function resetPasswordApi(token: string, password: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>('/auth/reset-password', { token, password });
  return data;
}

export interface RegisterPayload {
  email: string;
  password: string;
  partner_type?: 'individual' | 'legal' | 'entrepreneur';
  company_name: string;
  director_name: string;
  inn: string;
  phone: string;
  short_name?: string;
  full_legal_name?: string;
  legal_address?: string;
  postal_address?: string;
  kpp?: string;
  agent_code?: string;
  region: string;
  captcha_token?: string;
}

export interface RegisterResponse {
  message: string;
  user: { id: string; email: string; role: string };
}

export async function registerApi(payload: RegisterPayload): Promise<RegisterResponse> {
  const { data } = await apiClient.post<RegisterResponse>('/auth/register', payload);
  return data;
}
