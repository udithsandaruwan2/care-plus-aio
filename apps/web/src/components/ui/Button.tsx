import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Tone = 'primary' | 'ghost' | 'danger';

export function Button({
  children,
  tone = 'primary',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  tone?: Tone;
}) {
  const toneClass =
    tone === 'primary'
      ? 'bg-cyan text-inverse hover:brightness-95'
      : tone === 'danger'
        ? 'border border-rose/40 text-rose hover:bg-rose/10'
        : 'border border-hair text-mist hover:bg-soft';
  return (
    <button
      {...rest}
      className={`min-h-11 rounded-full px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${toneClass} ${className}`}
    >
      {children}
    </button>
  );
}

