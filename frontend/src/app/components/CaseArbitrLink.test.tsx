import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import CaseArbitrLink from './CaseArbitrLink';

afterEach(cleanup);

describe('CaseArbitrLink', () => {
  it('делает номер дела ссылкой на карточку в КАД Арбитр', () => {
    render(<CaseArbitrLink caseNumber="А66-5146/2026" />);

    const link = screen.getByRole('link', { name: /А66-5146\/2026/ });
    expect(link).toHaveAttribute(
      'href',
      'https://kad.arbitr.ru/Kad/Card?number=%D0%9066-5146%2F2026',
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('title', 'Открыть дело в КАД Арбитр');
  });

  it('открывает в новой вкладке и сообщает об этом скринридеру', () => {
    render(<CaseArbitrLink caseNumber="А66-5146/2026" />);
    expect(screen.getByRole('link')).toHaveAccessibleName(/открыть дело в КАД Арбитр/i);
  });

  it('показывает прочерк, если номер дела не заполнен', () => {
    render(<CaseArbitrLink caseNumber="" />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('поддерживает свой текст для пустого значения', () => {
    render(<CaseArbitrLink caseNumber={null} emptyLabel="Дело не указано" />);
    expect(screen.getByText('Дело не указано')).toBeInTheDocument();
  });

  it('использует сохранённую ссылку на карточку, если она передана', () => {
    const guid = 'https://kad.arbitr.ru/Card/eb01b4c8-c6bb-4d57-af07-52494311980d';
    render(<CaseArbitrLink caseNumber="А66-5146/2026" explicitUrl={guid} />);
    expect(screen.getByRole('link')).toHaveAttribute('href', guid);
  });

  it('не рендерит ссылку на непроверенный домен', () => {
    render(<CaseArbitrLink caseNumber="" explicitUrl="https://evil.example/Card/1" />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
