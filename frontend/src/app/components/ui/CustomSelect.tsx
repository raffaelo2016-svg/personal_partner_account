import { useState, useRef, useEffect, useCallback, useLayoutEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Check } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectOptionGroup {
  label: string;
  options: SelectOption[];
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options?: SelectOption[];
  groups?: SelectOptionGroup[];
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  required?: boolean;
  name?: string;
  searchable?: boolean;
  id?: string;
}

export default function CustomSelect({
  value,
  onChange,
  options,
  groups,
  placeholder = 'Выберите...',
  className = '',
  triggerClassName = '',
  size = 'md',
  disabled = false,
  searchable = false,
  id,
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null);
  const [highlightedValue, setHighlightedValue] = useState<string | null>(null);
  const listId = useId();
  const [menuStyle, setMenuStyle] = useState<{
    top: number;
    left: number;
    width: number;
    placement: 'bottom' | 'top';
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const allOptions: SelectOption[] =
    options ?? groups?.flatMap((g) => g.options) ?? [];

  const selectedOption = allOptions.find((o) => o.value === value);
  const normalize = (text: string) => text.toLocaleLowerCase('ru').replace(/ё/g, 'е').trim();
  const search = normalize(query ?? '');
  const matches = (option: SelectOption) => !searchable || normalize(option.label).includes(search);
  const filteredGroups = groups?.map((group) => ({
    ...group,
    options: group.options.filter(matches),
  })).filter((group) => group.options.length > 0);
  const filteredOptions = allOptions.filter(matches);
  const enabledOptions = filteredOptions.filter((option) => !option.disabled);
  const highlightedOption = enabledOptions.find((option) => option.value === highlightedValue)
    ?? (query !== null ? enabledOptions[0] : enabledOptions.find((option) => option.value === value));
  const optionId = (val: string) => `${listId}-option-${encodeURIComponent(val)}`;

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery(null);
    setHighlightedValue(null);
  }, []);

  const updatePosition = useCallback(() => {
    const trigger = inputRef.current ?? triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const GAP = 6;
    const APPROX_MENU_HEIGHT = 240; // max-h-60 = 15rem ≈ 240px
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const placement: 'bottom' | 'top' =
      spaceBelow < Math.min(APPROX_MENU_HEIGHT, 200) && spaceAbove > spaceBelow ? 'top' : 'bottom';
    setMenuStyle({
      top: placement === 'bottom' ? rect.bottom + GAP : rect.top - GAP,
      left: rect.left,
      width: rect.width,
      placement,
    });
  }, []);

  useLayoutEffect(() => {
    if (!isOpen) return;
    updatePosition();
  }, [isOpen, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        (containerRef.current && containerRef.current.contains(target)) ||
        (listRef.current && listRef.current.contains(target))
      ) {
        return;
      }
      close();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const handleReposition = () => updatePosition();
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isOpen, close, updatePosition]);

  useEffect(() => {
    if (isOpen && listRef.current) {
      const active = listRef.current.querySelector(
        searchable ? '[data-highlighted="true"]' : '[data-active="true"]',
      );
      if (active) active.scrollIntoView({ block: 'nearest' });
    }
  }, [isOpen, searchable, highlightedOption?.value]);

  const sizeClasses = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3 py-2.5 text-sm',
    lg: 'px-4 py-3 text-sm',
  };

  const handleSelect = (val: string) => {
    onChange(val);
    close();
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {searchable ? (
        <div className="relative">
          <input
            ref={inputRef}
            id={id}
            type="text"
            role="combobox"
            aria-label={id ? undefined : placeholder}
            aria-autocomplete="list"
            aria-expanded={isOpen}
            aria-controls={isOpen ? listId : undefined}
            aria-activedescendant={isOpen && highlightedOption ? optionId(highlightedOption.value) : undefined}
            autoComplete="off"
            disabled={disabled}
            placeholder={placeholder}
            value={query ?? selectedOption?.label ?? ''}
            onFocus={(event) => {
              setIsOpen(true);
              event.currentTarget.select();
            }}
            onClick={() => setIsOpen(true)}
            onBlur={close}
            onChange={(event) => {
              setQuery(event.target.value);
              setHighlightedValue(null);
              setIsOpen(true);
            }}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) return;
              if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                setIsOpen(true);
                if (enabledOptions.length === 0) return;
                const index = isOpen
                  ? enabledOptions.findIndex((option) => option.value === highlightedOption?.value)
                  : -1;
                const next = event.key === 'ArrowDown'
                  ? (index + 1) % enabledOptions.length
                  : (index <= 0 ? enabledOptions.length : index) - 1;
                setHighlightedValue(enabledOptions[next]?.value ?? null);
              } else if (event.key === 'Enter' && isOpen) {
                event.preventDefault();
                if (highlightedOption) handleSelect(highlightedOption.value);
              } else if (event.key === 'Escape' && isOpen) {
                event.preventDefault();
                event.stopPropagation();
                close();
              }
            }}
            className={`
              w-full bg-white border border-gray-200 rounded-xl ${sizeClasses[size]} pr-10
              text-gray-900 placeholder:text-gray-400 transition-all duration-200
              hover:border-gray-300 hover:shadow-sm
              focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400
              disabled:opacity-50 disabled:cursor-not-allowed
              ${triggerClassName}
            `}
          />
          <ChevronDown
            className={`pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          />
        </div>
      ) : <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`
          w-full flex items-center justify-between gap-2
          bg-white border border-gray-200 rounded-xl
          ${sizeClasses[size]}
          text-left
          transition-all duration-200
          hover:border-gray-300 hover:shadow-sm
          focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400
          disabled:opacity-50 disabled:cursor-not-allowed
          ${isOpen ? 'border-blue-400 ring-2 ring-blue-500/20 shadow-sm' : ''}
          ${triggerClassName}
        `}
      >
        <span className={`truncate ${selectedOption ? 'text-gray-900' : 'text-gray-400'}`}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>}

      {isOpen && menuStyle &&
        createPortal(
          <div
            ref={listRef}
            id={listId}
            role={searchable ? 'listbox' : undefined}
            aria-label={searchable ? placeholder : undefined}
            onMouseDown={searchable ? (event) => event.preventDefault() : undefined}
            className="
              fixed z-50
              bg-white border border-gray-200 rounded-xl
              shadow-lg shadow-gray-200/50
              max-h-60 overflow-y-auto
              py-1
              animate-in fade-in-0 zoom-in-95
            "
            style={{
              top: menuStyle.placement === 'bottom' ? menuStyle.top : undefined,
              bottom:
                menuStyle.placement === 'top'
                  ? window.innerHeight - menuStyle.top
                  : undefined,
              left: menuStyle.left,
              width: menuStyle.width,
              transformOrigin: menuStyle.placement === 'bottom' ? 'top' : 'bottom',
              animationDuration: '150ms',
            }}
          >
            {filteredOptions.length === 0 && (
              <div role="status" className="px-3 py-3 text-sm text-gray-500">
                Ничего не найдено
              </div>
            )}
            {filteredGroups
              ? filteredGroups.map((group) => (
                  <div key={group.label}>
                    <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                      {group.label}
                    </div>
                    {group.options.map((opt) => (
                      <OptionItem
                        key={opt.value}
                        option={opt}
                        isSelected={opt.value === value}
                        id={searchable ? optionId(opt.value) : undefined}
                        isHighlighted={searchable && opt.value === highlightedOption?.value}
                        onSelect={handleSelect}
                      />
                    ))}
                  </div>
                ))
              : filteredOptions.map((opt) => (
                  <OptionItem
                    key={opt.value}
                    option={opt}
                    isSelected={opt.value === value}
                    id={searchable ? optionId(opt.value) : undefined}
                    isHighlighted={searchable && opt.value === highlightedOption?.value}
                    onSelect={handleSelect}
                  />
                ))}
          </div>,
          document.body,
        )}
    </div>
  );
}

function OptionItem({
  option,
  isSelected,
  onSelect,
  id,
  isHighlighted,
}: {
  option: SelectOption;
  isSelected: boolean;
  onSelect: (val: string) => void;
  id?: string;
  isHighlighted?: boolean;
}) {
  return (
    <button
      type="button"
      id={id}
      role={id ? 'option' : undefined}
      aria-selected={id ? isSelected : undefined}
      tabIndex={id ? -1 : undefined}
      data-active={isSelected}
      data-highlighted={isHighlighted}
      disabled={option.disabled}
      onClick={() => onSelect(option.value)}
      className={`
        w-full flex items-center justify-between gap-2
        px-3 py-2 text-sm text-left
        transition-colors duration-100
        disabled:opacity-40 disabled:cursor-not-allowed
        ${
          isSelected || isHighlighted
            ? 'bg-blue-50 text-blue-700 font-medium'
            : 'text-gray-700 hover:bg-gray-50'
        }
      `}
    >
      <span className="truncate">{option.label}</span>
      {isSelected && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
    </button>
  );
}
