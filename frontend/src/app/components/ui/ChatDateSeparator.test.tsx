import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ChatDateSeparator from './ChatDateSeparator';

describe('ChatDateSeparator', () => {
  it('shows the date of the first message', () => {
    render(<ChatDateSeparator createdAt="2026-09-17T13:04:00Z" timezone="Europe/Moscow" />);
    expect(screen.getByRole('separator', { name: '17.09.2026' })).toBeTruthy();
  });

  it('does not repeat the date for messages on the same day', () => {
    render(<ChatDateSeparator createdAt="2026-09-17T14:32:00Z" previousCreatedAt="2026-09-17T13:04:00Z" timezone="Europe/Moscow" />);
    expect(screen.queryByRole('separator')).toBeNull();
  });

  it('uses the selected timezone across midnight', () => {
    render(<ChatDateSeparator createdAt="2026-09-17T22:05:00Z" previousCreatedAt="2026-09-17T20:55:00Z" timezone="Europe/Moscow" />);
    expect(screen.getByRole('separator', { name: '18.09.2026' })).toBeTruthy();
  });

  it('does not show a date when the timestamp is missing', () => {
    render(<ChatDateSeparator createdAt="" timezone="Europe/Moscow" />);
    expect(screen.queryByRole('separator')).toBeNull();
  });
});
