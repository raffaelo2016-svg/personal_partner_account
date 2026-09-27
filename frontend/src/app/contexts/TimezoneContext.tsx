import { createContext, useContext, type ReactNode } from 'react';
import { MOSCOW_TIME_ZONE } from '../utils/formatDate';

const TimezoneContext = createContext<string>(MOSCOW_TIME_ZONE);

export function TimezoneProvider({ children }: { children: ReactNode }) {
  return (
    <TimezoneContext.Provider value={MOSCOW_TIME_ZONE}>
      {children}
    </TimezoneContext.Provider>
  );
}

export function useTimezone(): string {
  return useContext(TimezoneContext);
}
