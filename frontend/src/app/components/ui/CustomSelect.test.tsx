import { useState, type FormEvent } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import CustomSelect from './CustomSelect';
import { REGION_GROUPS } from '../../data/arbitrageCourts';

const groups = REGION_GROUPS.map((group) => ({
  label: group.district,
  options: group.regions.map((region) => ({ value: region.name, label: region.name })),
}));

function RegionField({ initialValue = '' }: { initialValue?: string }) {
  const [value, setValue] = useState(initialValue);
  return <CustomSelect searchable value={value} onChange={setValue} groups={groups} placeholder="Регион" />;
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

describe('searchable region selection', () => {
  it('finds regions by part of the name regardless of case and hides empty districts', () => {
    render(<RegionField />);
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '  ТАТАР  ' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('option', { name: 'Республика Татарстан' })).toBeInTheDocument();
    expect(screen.queryByText('Центральный федеральный округ')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('option'));
    expect(input).toHaveValue('Республика Татарстан');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('selects with arrows and Enter without submitting the surrounding form', () => {
    const submit = vi.fn((event: FormEvent) => event.preventDefault());
    render(<form onSubmit={submit}><RegionField /></form>);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'моск' } });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(input).toHaveValue('Московская область');
    expect(submit).not.toHaveBeenCalled();
  });

  it.each(['Escape', 'blur', 'outside'])('keeps the saved region when an unfinished search is dismissed via %s', (action) => {
    render(<RegionField initialValue="Белгородская область" />);
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'моск' } });
    if (action === 'Escape') fireEvent.keyDown(input, { key: 'Escape' });
    else if (action === 'blur') fireEvent.blur(input);
    else fireEvent.mouseDown(document.body);
    expect(input).toHaveValue('Белгородская область');
    fireEvent.click(input);
    expect(screen.getAllByRole('option')).toHaveLength(groups.flatMap((group) => group.options).length);
  });

  it('shows an empty result and never saves arbitrary text', () => {
    const change = vi.fn();
    render(<CustomSelect searchable value="" onChange={change} groups={groups} />);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'Несуществующий регион' } });
    expect(screen.getByRole('status')).toHaveTextContent('Ничего не найдено');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(change).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: '' } });
    expect(screen.getAllByRole('option')).toHaveLength(groups.flatMap((group) => group.options).length);
  });

  it('does not select disabled matches', () => {
    const change = vi.fn();
    render(<CustomSelect searchable value="" onChange={change} options={[
      { value: 'one', label: 'Регион 1', disabled: true },
      { value: 'two', label: 'Регион 2' },
    ]} />);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'Регион' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(change).toHaveBeenCalledWith('two');
  });

  it('preserves the existing button select when search is not enabled', () => {
    const change = vi.fn();
    render(<CustomSelect value="" onChange={change} groups={groups} />);
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button', { name: 'Белгородская область' }));
    expect(change).toHaveBeenCalledWith('Белгородская область');
  });
});
