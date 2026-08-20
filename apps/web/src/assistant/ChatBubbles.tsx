import { useEffect, useState } from 'react';
import type { ChatMessage } from './store';
import type { TurnFailure } from './turnFailure';

type Props = {
  messages: ChatMessage[];
  compact?: boolean;
  /** Step 86 — failed turn recovery affordance. */
  failure?: TurnFailure | null;
  onRetry?: () => void;
  retrying?: boolean;
};

/** Scrollable Serah ↔ patient thread (Step 15h / 87 progressive replies). */
export function ChatBubbles({
  messages,
  compact = false,
  failure = null,
  onRetry,
  retrying = false,
}: Props) {
  if (!messages.length && !failure) return null;
  const visible = compact ? messages.slice(-3) : messages;

  return (
    <div
      className={`flex w-full flex-col gap-1.5 overflow-y-auto px-1 ${
        compact ? 'mt-0 max-h-full max-w-lg' : 'mt-4 max-h-52 max-w-md'
      }`}
      aria-live="polite"
      aria-relevant="additions text"
      aria-label="Conversation with Serah"
    >
      {visible.map((msg) => (
        <Bubble key={msg.id} msg={msg} compact={compact} />
      ))}
      {failure ? (
        <div
          className={`rounded-xl border px-3 py-2 text-sm ${
            failure.kind === 'throttle'
              ? 'border-amber/40 bg-amber/5 text-amber'
              : 'border-rose/40 bg-rose/5 text-rose'
          }`}
          role="alert"
        >
          <p>{failure.message}</p>
          {failure.canRetry && onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retrying}
              className="mt-2 rounded-lg bg-rose/20 px-3 py-1 text-xs font-semibold text-mist ring-1 ring-rose/30 disabled:opacity-50"
            >
              {retrying ? 'Retrying…' : 'Retry message'}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Bubble({ msg, compact = false }: { msg: ChatMessage; compact?: boolean }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl leading-relaxed ${
          compact ? 'px-3 py-2 text-sm' : 'px-3.5 py-2 text-sm'
        } ${
          isUser
            ? 'rounded-br-md bg-cyan/15 text-mist ring-1 ring-cyan/25'
            : 'rounded-bl-md bg-soft text-mist ring-1 ring-hair'
        }`}
      >
        {!isUser && !compact && (
          <p className="mb-0.5 font-display text-[10px] uppercase tracking-wider text-cyan/80">
            Serah
          </p>
        )}
        {isUser ? <p>{msg.text}</p> : <ProgressiveText text={msg.text} />}
      </div>
    </div>
  );
}

/** Reveal Serah's reply word-by-word so stream-arriving text feels progressive (Step 87). */
function ProgressiveText({ text }: { text: string }) {
  const [shown, setShown] = useState(() => (text.length < 48 ? text : ''));

  useEffect(() => {
    if (!text) {
      setShown('');
      return;
    }
    if (text.length < 48) {
      setShown(text);
      return;
    }
    const words = text.split(/(\s+)/);
    let i = 0;
    setShown('');
    const id = window.setInterval(() => {
      i += 1;
      setShown(words.slice(0, i).join(''));
      if (i >= words.length) window.clearInterval(id);
    }, 28);
    return () => window.clearInterval(id);
  }, [text]);

  return (
    <p>
      <span aria-hidden>
        {shown}
        {shown.length < text.length ? (
          <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-cyan/70 align-middle" />
        ) : null}
      </span>
      <span className="sr-only">{text}</span>
    </p>
  );
}
