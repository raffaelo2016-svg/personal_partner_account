import { describe, it, expect } from 'vitest';

import { filesCountLabel, pluralFiles, pluralRu, selectedFilesLabel } from '../plural';

describe('pluralRu', () => {
  it.each([
    [1, 'файл'],
    [2, 'файла'],
    [4, 'файла'],
    [5, 'файлов'],
    [11, 'файлов'],
    [12, 'файлов'],
    [14, 'файлов'],
    [21, 'файл'],
    [22, 'файла'],
    [25, 'файлов'],
    [101, 'файл'],
    [111, 'файлов'],
  ])('%i → %s', (count, expected) => {
    expect(pluralFiles(count)).toBe(expected);
  });

  it('поддерживает произвольные формы', () => {
    expect(pluralRu(1, 'документ', 'документа', 'документов')).toBe('документ');
    expect(pluralRu(3, 'документ', 'документа', 'документов')).toBe('документа');
    expect(pluralRu(8, 'документ', 'документа', 'документов')).toBe('документов');
  });
});

describe('подписи для партнёра', () => {
  it('счётчик в карточке', () => {
    expect(filesCountLabel(1)).toBe('1 файл');
    expect(filesCountLabel(3)).toBe('3 файла');
    expect(filesCountLabel(12)).toBe('12 файлов');
  });

  it('заголовок выбранных файлов', () => {
    expect(selectedFilesLabel(0)).toBe('Файлы не выбраны');
    expect(selectedFilesLabel(1)).toBe('Выбран 1 файл');
    expect(selectedFilesLabel(3)).toBe('Выбрано 3 файла');
    expect(selectedFilesLabel(25)).toBe('Выбрано 25 файлов');
  });
});
