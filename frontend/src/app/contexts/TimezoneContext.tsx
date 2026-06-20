import { createContext, useContext, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { useAuthStore } from '../store/authStore';

const DEFAULT_TZ = 'Europe/Moscow';

async function fetchTz(): Promise<string> {
  try {
    const { data } = await apiClient.get('/settings/timezone');
    return data.timezone || DEFAULT_TZ;
  } catch {
    return DEFAULT_TZ;
  }
}

const TimezoneContext = createContext<string>(DEFAULT_TZ);

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const { data: tz } = useQuery({
    queryKey: ['appTimezone'],
    queryFn: fetchTz,
    enabled: !!accessToken,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  return (
    <TimezoneContext.Provider value={tz ?? DEFAULT_TZ}>
      {children}
    </TimezoneContext.Provider>
  );
}

export function useTimezone(): string {
  return useContext(TimezoneContext);
}
