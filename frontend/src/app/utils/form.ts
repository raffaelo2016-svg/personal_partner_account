/**
 * Создаёт синтетический event для кастомных компонентов (DateInput, CustomSelect)
 * чтобы переиспользовать handleChange без `as any`.
 */
export function syntheticChange(name: string, value: string) {
  return { target: { name, value } } as React.ChangeEvent<HTMLInputElement>;
}
