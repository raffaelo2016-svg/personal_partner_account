import { z } from 'zod';

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const clientFormSchema = z.object({
  fullName: z.string().min(1, 'Обязательное поле'),
  email: z
    .string()
    .trim()
    .optional()
    .refine((v) => !v || emailRegex.test(v), 'Некорректный email'),
});

export type ClientFormData = z.infer<typeof clientFormSchema>;
