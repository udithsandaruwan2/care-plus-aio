import { FormEvent, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Mic, Send } from 'lucide-react';
import { AssistantState } from '@care-plus/core';
import { useAssistant } from '../../assistant/store';
import { useSerahEngine } from '../../assistant/SerahEngine';
import { stateCopy } from '../../assistant/locale';
import '../../assistant/SerahHud.css';

/**
 * Bottom-right companion while the user is on another hub page.
 * Same live session as Serah Core — still listening, still matching.
 */
export function AIAssistantDock() {
  const location = useLocation();
  const { matching, asleep, sessionLive, chat, state, uiLanguage } = useAssistant();
  const engine = useSerahEngine();
  const [open, setOpen] = useState(true);
  const [line, setLine] = useState('');

  if (!sessionLive || location.pathname === '/app') return null;

  const last = chat.at(-1);
  const status = asleep
    ? 'Sleeping — say Hey Serah'
    : matching
      ? 'Finding caregivers…'
      : engine.listening
        ? 'Listening…'
        : stateCopy(state, uiLanguage);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = line.trim();
    if (!text) return;
    setLine('');
    await engine.submitText(text);
  }

  if (!open) {
    return (
      <button
        type="button"
        className="serah-dock-fab"
        onClick={() => setOpen(true)}
        aria-label="Open Serah companion"
      >
        <span className={`serah-dock-orb-mini ${engine.listening ? 'live' : ''} ${asleep ? 'sleep' : ''}`} />
        <span>Serah</span>
      </button>
    );
  }

  return (
    <aside className="serah-dock" aria-label="Serah companion">
      <header className="serah-dock-head">
        <span className={`serah-dock-orb-mini ${engine.listening ? 'live' : ''} ${asleep ? 'sleep' : ''}`} />
        <div className="min-w-0 flex-1">
          <p className="font-display text-sm text-cyan">Serah Core</p>
          <p className="truncate text-[11px] text-muted">{status}</p>
        </div>
        <button
          type="button"
          className="text-[11px] text-muted hover:text-mist"
          onClick={() => setOpen(false)}
        >
          Hide
        </button>
      </header>

      {matching ? (
        <div className="px-3 pt-2">
          <div className="match-search-track" role="progressbar" aria-label="Searching caregivers">
            <div className="match-search-fill match-search-fill-indeterminate" />
          </div>
          <p className="mt-1 text-[11px] text-muted">VEHMF is ranking caregivers…</p>
        </div>
      ) : null}

      {last ? (
        <p className="serah-dock-last">
          <span className="text-cyan">{last.role === 'serah' ? 'Serah' : 'You'}: </span>
          {last.text}
        </p>
      ) : (
        <p className="serah-dock-last text-muted">The core is working with you.</p>
      )}

      <form className="serah-dock-form" onSubmit={(e) => void onSubmit(e)}>
        <button
          type="button"
          onClick={() => void engine.toggleMic()}
          aria-pressed={engine.listening}
          aria-label={engine.listening ? 'Stop listening' : 'Talk to Serah'}
          className={`serah-dock-mic ${engine.listening ? 'active' : ''}`}
        >
          <Mic size={16} />
        </button>
        <input
          value={line}
          onChange={(e) => setLine(e.target.value)}
          placeholder={asleep ? 'Hey Serah…' : 'Ask Serah…'}
          disabled={engine.listening}
          className="min-h-9 flex-1 rounded-lg border border-hair bg-panel px-2.5 text-xs text-mist outline-none focus:border-cyan"
        />
        <button
          type="submit"
          disabled={!line.trim() || engine.listening}
          className="rounded-lg bg-cyan px-2.5 text-xs font-semibold text-inverse disabled:opacity-40"
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </form>

      <div className="flex items-center justify-between px-3 pb-2">
        <Link to="/app" className="text-[11px] font-semibold text-cyan hover:underline">
          Open Serah Core
        </Link>
        {engine.busy && state === AssistantState.THINKING ? (
          <span className="text-[11px] text-muted">Replying…</span>
        ) : null}
      </div>
    </aside>
  );
}
