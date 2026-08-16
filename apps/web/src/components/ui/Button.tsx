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
      ? 'bg-cyan text-inverse shadow-sm hover:brightness-95'
      : tone === 'danger'
        ? 'border border-rose/40 text-rose hover:bg-rose/10'
        : 'border border-hair bg-panel text-mist hover:bg-soft';
  return (
    <button
      {...rest}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${toneClass} ${className}`}
    >
      {children}
    </button>
  );
}
