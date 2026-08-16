import type { InputHTMLAttributes } from 'react';

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`min-h-11 w-full rounded-xl border border-hair bg-panel px-3.5 py-2.5 text-sm text-mist outline-none placeholder:text-muted focus:border-cyan focus:ring-2 focus:ring-cyan/20 ${props.className ?? ''}`}
    />
  );
}
