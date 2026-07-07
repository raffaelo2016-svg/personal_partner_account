import { z } from 'zod';

const REQUIRED = 'Обязательное поле';

export const registrationStep1Schema = z.object({
  companyName: z.string().min(1, REQUIRED),
  inn: z
    .string()
    .min(1, REQUIRED)
    .regex(/^\d{10}$/, 'ИНН должен содержать 10 цифр'),
  ogrn: z
    .string()
    .min(1, REQUIRED)
    .regex(/^\d{13}$/, 'ОГРН должен содержать 13 цифр'),
  legalAddress: z.string().min(1, REQUIRED),
});

export const registrationStep2Schema = z
  .object({
    contactName: z.string().min(1, REQUIRED),
    contactEmail: z
      .string()
      .min(1, REQUIRED)
      .regex(/^[^\s@]+@[^\s@]+\.[^\s@]+$/, 'Некорректный email'),
    password: z.string().min(1, REQUIRED).min(8, 'Минимум 8 символов'),
    confirmPassword: z.string().min(1, REQUIRED),
    agreeTerms: z.literal(true, { errorMap: () => ({ message: 'Необходимо согласие' }) }),
    agreePersonalData: z.literal(true, {
      errorMap: () => ({ message: 'Необходимо согласие' }),
    }),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Пароли не совпадают',
    path: ['confirmPassword'],
  });

export type RegistrationStep1 = z.infer<typeof registrationStep1Schema>;
export type RegistrationStep2 = z.infer<typeof registrationStep2Schema>;

export function flattenZodErrors<T>(result: z.SafeParseReturnType<unknown, T>): Record<string, string> {
  if (result.success) return {};
  const out: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path[0];
    if (typeof key === 'string' && !(key in out)) {
      out[key] = issue.message;
    }
  }
  return out;
}
