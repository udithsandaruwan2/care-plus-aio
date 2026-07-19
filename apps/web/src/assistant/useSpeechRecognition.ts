import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export type RecognitionLang = 'si-LK' | 'ta-LK' | 'en-US';

export type SpeechControls = {
  supported: boolean;
  listening: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
};

type Handlers = {
  lang: RecognitionLang;
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  /** Fired when recognition ends (pause after speech, or manual stop). */
  onEnd: () => void;
};

function getCtor(): SpeechRecognitionConstructor | null {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * Web Speech captions. Uses non-continuous mode so a natural pause ends the
 * utterance and triggers ``onEnd`` → conversational turn (THINKING / Serah).
 *
 * ``continuous: true`` was stranding users in LISTENING forever because Chrome
 * rarely auto-ends; the turn never reached the server.
 */
export function useSpeechRecognition(handlers: Handlers): SpeechControls {
  const supported = useMemo(() => getCtor() !== null, []);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recRef = useRef<SpeechRecognition | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hRef = useRef(handlers);
  hRef.current = handlers;

  const clearSilence = () => {
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current);
      silenceTimer.current = null;
    }
  };

  const stop = useCallback(() => {
    clearSilence();
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = getCtor();
    if (!Ctor) {
      setError('Speech recognition is not supported in this browser.');
      return;
    }
    setError(null);
    clearSilence();

    const rec = new Ctor();
    rec.lang = hRef.current.lang;
    // One utterance per turn — pause ends recognition and fires onEnd.
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (event) => {
      let interim = '';
      let sawFinal = false;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? '';
        if (result.isFinal) {
          sawFinal = true;
          hRef.current.onFinal(text.trim());
        } else {
          interim += text;
        }
      }
      if (interim) hRef.current.onInterim(interim.trim());

      // Some browsers linger after a final result; force-end after a short pause.
      if (sawFinal) {
        clearSilence();
        silenceTimer.current = setTimeout(() => {
          try {
            rec.stop();
          } catch {
            /* already stopped */
          }
        }, 900);
      }
    };

    rec.onerror = (event) => {
      if (event.error === 'no-speech') return;
      if (event.error === 'not-allowed') setError('Microphone permission denied.');
      else if (event.error !== 'aborted') setError(`Speech error: ${event.error}`);
    };

    rec.onend = () => {
      clearSilence();
      setListening(false);
      recRef.current = null;
      hRef.current.onEnd();
    };

    recRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      setError('Could not start speech recognition.');
    }
  }, []);

  useEffect(
    () => () => {
      clearSilence();
      recRef.current?.abort();
    },
    [],
  );

  return { supported, listening, error, start, stop };
}
