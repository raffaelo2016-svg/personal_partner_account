import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

import { PartnerLocalTime } from './PartnerLocalTime';

describe('PartnerLocalTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-27T18:34:00Z'));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('показывает время, смещение и регион партнёра', () => {
    render(<PartnerLocalTime region="Красноярский край" />);

    expect(screen.getByText('01:34')).toBeInTheDocument();
    expect(screen.getByText('UTC+7 · Красноярский край')).toBeInTheDocument();
    expect(screen.getByText('Сейчас у партнёра')).toBeInTheDocument();
  });

  it('без региона показывает Москву', () => {
    render(<PartnerLocalTime region={null} />);

    expect(screen.getByText('21:34')).toBeInTheDocument();
    expect(screen.getByText('UTC+3 · Москва')).toBeInTheDocument();
  });

  it('обновляет время без перезагрузки страницы', () => {
    render(<PartnerLocalTime region="Москва" />);
    expect(screen.getByText('21:34')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(60 * 60 * 1000);
    });

    expect(screen.getByText('22:34')).toBeInTheDocument();
  });
});
