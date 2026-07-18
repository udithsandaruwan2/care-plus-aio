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
  /** Fired when recognition ends (e.g. detected silence / stopped). */
  onEnd: () => void;
};

function getCtor(): SpeechRecognitionConstructor | null {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * Web Speech API wrapper. Streams interim results and commits final segments.
 * On `end` (silence or manual stop) it calls `onEnd` so the FSM can move to
 * THINKING. Language is switchable for Sinhala / Tamil / English.
 */
export function useSpeechRecognition(handlers: Handlers): SpeechControls {
  const supported = useMemo(() => getCtor() !== null, []);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recRef = useRef<SpeechRecognition | null>(null);
  const manualStop = useRef(false);
  // Keep latest handlers without re-creating the recognizer.
  const hRef = useRef(handlers);
  hRef.current = handlers;

  const stop = useCallback(() => {
    manualStop.current = true;
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = getCtor();
    if (!Ctor) {
      setError('Speech recognition is not supported in this browser.');
      return;
    }
    setError(null);
    manualStop.current = false;

    const rec = new Ctor();
    rec.lang = hRef.current.lang;
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? '';
        if (result.isFinal) hRef.current.onFinal(text.trim());
        else interim += text;
      }
      if (interim) hRef.current.onInterim(interim.trim());
    };

    rec.onerror = (event) => {
      if (event.error === 'no-speech') return;
      if (event.error === 'not-allowed') setError('Microphone permission denied.');
      else if (event.error !== 'aborted') setError(`Speech error: ${event.error}`);
    };

    rec.onend = () => {
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
      manualStop.current = true;
      recRef.current?.abort();
    },
    [],
  );

  return { supported, listening, error, start, stop };
}
