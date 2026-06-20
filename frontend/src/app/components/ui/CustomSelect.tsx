import { useState, useRef, useEffect, useCallback, useLayoutEffect } from 'react';
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
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<{
    top: number;
    left: number;
    width: number;
    placement: 'bottom' | 'top';
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const allOptions: SelectOption[] =
    options ?? groups?.flatMap((g) => g.options) ?? [];

  const selectedOption = allOptions.find((o) => o.value === value);

  const close = useCallback(() => setIsOpen(false), []);

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
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
      const active = listRef.current.querySelector('[data-active="true"]');
      if (active) active.scrollIntoView({ block: 'nearest' });
    }
  }, [isOpen]);

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
      <button
        ref={triggerRef}
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
      </button>

      {isOpen && menuStyle &&
        createPortal(
          <div
            ref={listRef}
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
            {groups
              ? groups.map((group) => (
                  <div key={group.label}>
                    <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                      {group.label}
                    </div>
                    {group.options.map((opt) => (
                      <OptionItem
                        key={opt.value}
                        option={opt}
                        isSelected={opt.value === value}
                        onSelect={handleSelect}
                      />
                    ))}
                  </div>
                ))
              : allOptions.map((opt) => (
                  <OptionItem
                    key={opt.value}
                    option={opt}
                    isSelected={opt.value === value}
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
}: {
  option: SelectOption;
  isSelected: boolean;
  onSelect: (val: string) => void;
}) {
  return (
    <button
      type="button"
      data-active={isSelected}
      disabled={option.disabled}
      onClick={() => onSelect(option.value)}
      className={`
        w-full flex items-center justify-between gap-2
        px-3 py-2 text-sm text-left
        transition-colors duration-100
        disabled:opacity-40 disabled:cursor-not-allowed
        ${
          isSelected
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
