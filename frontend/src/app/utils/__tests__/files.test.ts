import { describe, it, expect } from 'vitest';
import { partitionFiles, formatFileSize, uploadAllSettled, MAX_FILE_SIZE_BYTES } from '../files';

function makeFile(name: string, size: number, type = ''): File {
  const blob = new Blob([new Uint8Array(size)], { type });
  return new File([blob], name, { type });
}

describe('partitionFiles', () => {
  it.each(['application/zip', 'application/x-zip-compressed', ''])('принимает ZIP с MIME %s', (type) => {
    const file = makeFile('documents.ZIP', 100, type);
    expect(partitionFiles([file]).valid).toEqual([file]);
  });

  it('отвергает ZIP больше лимита', () => {
    const file = makeFile('documents.zip', MAX_FILE_SIZE_BYTES + 1, 'application/zip');
    expect(partitionFiles([file]).tooLarge).toEqual(['documents.zip']);
  });

  it('принимает разрешённые форматы по MIME', () => {
    const f = makeFile('a.pdf', 100, 'application/pdf');
    const r = partitionFiles([f]);
    expect(r.valid).toEqual([f]);
    expect(r.invalidFormat).toEqual([]);
    expect(r.tooLarge).toEqual([]);
  });

  it('принимает разрешённые форматы по расширению, если MIME пустой', () => {
    const f = makeFile('a.docx', 100);
    const r = partitionFiles([f]);
    expect(r.valid).toEqual([f]);
  });

  it('отвергает запрещённый формат', () => {
    const f = makeFile('virus.exe', 100, 'application/x-msdownload');
    const r = partitionFiles([f]);
    expect(r.invalidFormat).toEqual(['virus.exe']);
    expect(r.valid).toEqual([]);
  });

  it('отвергает превышение размера', () => {
    const f = makeFile('big.pdf', MAX_FILE_SIZE_BYTES + 1, 'application/pdf');
    const r = partitionFiles([f]);
    expect(r.tooLarge).toEqual(['big.pdf']);
    expect(r.valid).toEqual([]);
  });

  it('разделяет смешанный набор', () => {
    const ok = makeFile('ok.png', 10, 'image/png');
    const bad = makeFile('bad.exe', 10);
    const big = makeFile('big.pdf', MAX_FILE_SIZE_BYTES + 1, 'application/pdf');
    const r = partitionFiles([ok, bad, big]);
    expect(r.valid).toEqual([ok]);
    expect(r.invalidFormat).toEqual(['bad.exe']);
    expect(r.tooLarge).toEqual(['big.pdf']);
  });

  it('отвергает файл без расширения и без MIME', () => {
    const f = makeFile('README', 10);
    const r = partitionFiles([f]);
    expect(r.invalidFormat).toEqual(['README']);
    expect(r.valid).toEqual([]);
  });

  it('принимает файл ровно на границе MAX_FILE_SIZE_BYTES', () => {
    const f = makeFile('edge.pdf', MAX_FILE_SIZE_BYTES, 'application/pdf');
    const r = partitionFiles([f]);
    expect(r.valid).toEqual([f]);
  });

  it('обрабатывает FileList-подобный объект через Array.from', () => {
    const a = makeFile('a.pdf', 5, 'application/pdf');
    const b = makeFile('b.png', 5, 'image/png');
    const fileList = {
      0: a,
      1: b,
      length: 2,
      item: (i: number) => [a, b][i] ?? null,
      [Symbol.iterator]: function* () {
        yield a;
        yield b;
      },
    } as unknown as FileList;
    const r = partitionFiles(fileList);
    expect(r.valid).toEqual([a, b]);
  });

  it('корректно учитывает регистр расширения', () => {
    const f = makeFile('photo.JPG', 10);
    const r = partitionFiles([f]);
    expect(r.valid).toEqual([f]);
  });
});

describe('formatFileSize', () => {
  it('возвращает 0 Bytes для нуля', () => {
    expect(formatFileSize(0)).toBe('0 Bytes');
  });
  it('форматирует KB', () => {
    expect(formatFileSize(2048)).toBe('2 KB');
  });
  it('форматирует MB', () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5 MB');
  });

  it('форматирует GB', () => {
    expect(formatFileSize(3 * 1024 * 1024 * 1024)).toBe('3 GB');
  });

  it('сохраняет два знака после запятой для некруглых значений', () => {
    expect(formatFileSize(1536)).toBe('1.5 KB');
  });

  it('форматирует байты меньше килобайта', () => {
    expect(formatFileSize(512)).toBe('512 Bytes');
  });
});

describe('uploadAllSettled', () => {
  it('собирает успехи и провалы', async () => {
    const items = ['a', 'b', 'c'];
    const r = await uploadAllSettled(items, async (x) => {
      if (x === 'b') throw new Error('boom');
      return x;
    });
    expect(r.succeeded).toEqual(['a', 'c']);
    expect(r.failed).toHaveLength(1);
    expect(r.failed[0].item).toBe('b');
    expect((r.failed[0].error as Error).message).toBe('boom');
  });

  it('возвращает пустые массивы для пустого входа', async () => {
    const r = await uploadAllSettled([], async () => undefined);
    expect(r.succeeded).toEqual([]);
    expect(r.failed).toEqual([]);
  });

  it('сохраняет не-Error rejection как есть', async () => {
    const r = await uploadAllSettled(['x'], async () => {
      throw 'plain string';
    });
    expect(r.succeeded).toEqual([]);
    expect(r.failed).toHaveLength(1);
    expect(r.failed[0].error).toBe('plain string');
  });

  it('сохраняет порядок item в succeeded/failed', async () => {
    const r = await uploadAllSettled(['a', 'b', 'c', 'd'], async (x) => {
      if (x === 'a' || x === 'c') throw new Error('no');
      return x;
    });
    expect(r.succeeded).toEqual(['b', 'd']);
    expect(r.failed.map((f) => f.item)).toEqual(['a', 'c']);
  });
});
