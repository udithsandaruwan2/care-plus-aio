import type { ChatMessage } from './store';

type Props = {
  messages: ChatMessage[];
  compact?: boolean;
};

/** Scrollable Serah ↔ patient thread (Step 15h). */
export function ChatBubbles({ messages, compact = false }: Props) {
  if (!messages.length) return null;
  const visible = compact ? messages.slice(-3) : messages;

  return (
    <div
      className={`flex w-full flex-col gap-1.5 overflow-y-auto px-1 ${
        compact ? 'mt-0 max-h-full max-w-lg' : 'mt-4 max-h-52 max-w-md'
      }`}
      aria-live="polite"
      aria-label="Conversation with Serah"
    >
      {visible.map((msg) => (
        <Bubble key={msg.id} msg={msg} compact={compact} />
      ))}
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
        <p>{msg.text}</p>
      </div>
    </div>
  );
}
