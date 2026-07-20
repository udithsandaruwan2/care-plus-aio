import type { ChatMessage } from './store';

type Props = {
  messages: ChatMessage[];
};

/** Scrollable Serah ↔ patient thread (Step 15h). */
export function ChatBubbles({ messages }: Props) {
  if (!messages.length) return null;

  return (
    <div
      className="mt-4 flex max-h-52 w-full max-w-md flex-col gap-2 overflow-y-auto px-1"
      aria-live="polite"
      aria-label="Conversation with Serah"
    >
      {messages.map((msg) => (
        <Bubble key={msg.id} msg={msg} />
      ))}
    </div>
  );
}

function Bubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
          isUser
            ? 'rounded-br-md bg-cyan/15 text-mist ring-1 ring-cyan/25'
            : 'rounded-bl-md bg-panel/90 text-mint ring-1 ring-hair'
        }`}
      >
        {!isUser && (
          <p className="mb-0.5 font-display text-[10px] uppercase tracking-wider text-cyan/80">
            Serah
          </p>
        )}
        <p>{msg.text}</p>
      </div>
    </div>
  );
}
