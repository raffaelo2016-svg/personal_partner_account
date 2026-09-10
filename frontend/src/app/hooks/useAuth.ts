import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  forgotPasswordApi,
  getMeApi,
  loginApi,
  logoutApi,
  resetPasswordApi,
  type LoginPayload,
} from '@/app/api/auth';
import { useAuthStore } from '@/app/store/authStore';

export function useLogin() {
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (payload: LoginPayload) => loginApi(payload),
    onSuccess: (data) => {
      login(
        { id: data.user.id, email: data.user.email, role: data.user.role },
        data.access_token,
      );
      navigate(data.user.role === 'admin' ? '/admin' : '/dashboard');
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => logoutApi(),
    onSettled: () => {
      logout();
      queryClient.clear();
      navigate('/login');
    },
  });
}

export function useMe() {
  const accessToken = useAuthStore((s) => s.accessToken);

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMeApi,
    enabled: !!accessToken,
    staleTime: 5 * 60_000,
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) => forgotPasswordApi(email),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ token, password }: { token: string; password: string }) =>
      resetPasswordApi(token, password),
  });
}
