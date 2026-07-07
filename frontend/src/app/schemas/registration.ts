import { z } from 'zod';

const REQUIRED = 'Обязательное поле';

export const registrationStep1Schema = z.object({
  partnerType: z.enum(['individual', 'legal', 'entrepreneur']),
  companyName: z.string().optional(),
  lastName: z.string().optional(),
  firstName: z.string().optional(),
  middleName: z.string().optional(),
  inn: z.string().optional(),
  ogrn: z.string().optional(),
  legalAddress: z.string().optional(),
}).superRefine((data, ctx) => {
  const add = (path: string, message = REQUIRED) => {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
  };

  if (data.partnerType === 'legal') {
    if (!data.companyName) add('companyName');
    if (!data.legalAddress) add('legalAddress');
    if (!data.inn) add('inn');
    else if (!/^\d{10}$/.test(data.inn)) add('inn', 'ИНН должен содержать 10 цифр');
    if (!data.ogrn) add('ogrn');
    else if (!/^\d{13}$/.test(data.ogrn)) add('ogrn', 'ОГРН должен содержать 13 цифр');
    return;
  }

  if (!data.lastName) add('lastName');
  if (!data.firstName) add('firstName');

  if (data.partnerType === 'entrepreneur') {
    if (!data.inn) add('inn');
    else if (!/^\d{12}$/.test(data.inn)) add('inn', 'ИНН должен содержать 12 цифр');
  }
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
