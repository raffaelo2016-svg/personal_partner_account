import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import CaseNumberCard from './CaseNumberCard';

afterEach(cleanup);

describe('CaseNumberCard', () => {
  it('показывает прочерк и предложение добавить номер', () => {
    render(<CaseNumberCard value={null} onSave={vi.fn()} />);

    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /добавить номер/i })).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('считает сохранённую заглушку пустым номером', () => {
    render(<CaseNumberCard value="—" onSave={vi.fn()} />);

    expect(screen.getByRole('button', { name: /добавить номер/i })).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('сохраняет номер без пробелов и в верхнем регистре', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<CaseNumberCard value={null} onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /добавить номер/i }));
    fireEvent.change(screen.getByLabelText('Номер дела'), {
      target: { value: ' а66-5146 / 2026 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith('А66-5146/2026'));
  });

  it('показывает существующий номер ссылкой на КАД и открывает редактирование', () => {
    render(<CaseNumberCard value="А66-5146/2026" onSave={vi.fn()} />);

    expect(screen.getByRole('link', { name: /А66-5146\/2026/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Изменить номер дела' }));

    expect(screen.getByLabelText('Номер дела')).toHaveValue('А66-5146/2026');
  });

  it('не сохраняет номер без цифр и показывает ошибку', () => {
    const onSave = vi.fn();
    render(<CaseNumberCard value={null} onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /добавить номер/i }));
    fireEvent.change(screen.getByLabelText('Номер дела'), { target: { value: 'дело' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(screen.getByRole('alert')).toHaveTextContent('В номере дела должны быть цифры');
    expect(onSave).not.toHaveBeenCalled();
  });

  it('очищает номер, если сохранить пустое поле', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<CaseNumberCard value="А66-5146/2026" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить номер дела' }));
    fireEvent.change(screen.getByLabelText('Номер дела'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(null));
  });

  it('закрывает редактирование по Escape без сохранения', () => {
    const onSave = vi.fn();
    render(<CaseNumberCard value="А66-5146/2026" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить номер дела' }));
    fireEvent.keyDown(screen.getByLabelText('Номер дела'), { key: 'Escape' });

    expect(screen.queryByLabelText('Номер дела')).not.toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('остаётся в редактировании, если сохранение не удалось', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('fail'));
    render(<CaseNumberCard value="А66-5146/2026" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить номер дела' }));
    fireEvent.change(screen.getByLabelText('Номер дела'), {
      target: { value: 'А66-9999/2026' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Не удалось сохранить номер дела'),
    );
    expect(screen.getByLabelText('Номер дела')).toHaveValue('А66-9999/2026');
  });
});
