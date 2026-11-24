export function pluralRu(count: number, one: string, few: string, many: string): string {
  const abs = Math.abs(count) % 100;
  if (abs >= 11 && abs <= 14) return many;
  const last = abs % 10;
  if (last === 1) return one;
  if (last >= 2 && last <= 4) return few;
  return many;
}

export function pluralFiles(count: number): string {
  return pluralRu(count, 'файл', 'файла', 'файлов');
}

/** «1 файл», «3 файла», «25 файлов» — с числом. */
export function filesCountLabel(count: number): string {
  return `${count} ${pluralFiles(count)}`;
}

/** Заголовок над списком выбранных документов. */
export function selectedFilesLabel(count: number): string {
  if (count === 0) return 'Файлы не выбраны';
  if (count === 1) return 'Выбран 1 файл';
  return `Выбрано ${filesCountLabel(count)}`;
}
