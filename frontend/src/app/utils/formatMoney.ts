/**
 * Converts kopecks (int) to a formatted ruble string.
 * Example: 1_500_000 → "15 000 ₽"
 */
export function formatMoney(kopecks: number): string {
  const rubles = kopecks / 100;
  return rubles.toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }) + ' ₽';
}
