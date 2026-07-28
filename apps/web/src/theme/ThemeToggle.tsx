import { useTheme } from './ThemeProvider';

const ORDER = ['light', 'dark', 'system'] as const;

export function ThemeToggle() {
  const { mode, resolved, setMode } = useTheme();

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-hair bg-panel px-1 py-1 text-xs shadow-[var(--cp-shadow-soft)]">
      {ORDER.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => setMode(opt)}
          className={`rounded-full px-2.5 py-1 capitalize transition ${
            mode === opt
              ? 'bg-elevated text-mist'
              : 'text-muted hover:bg-soft hover:text-mist'
          }`}
          title={opt === 'system' ? `System (${resolved})` : undefined}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

