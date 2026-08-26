import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { shouldPublishAmplitude } from './frameBudget';

export type MicStartOptions = {
  /**
   * During Serah TTS: disable AGC so distant room voices are not boosted into
   * barge-in range; keep echoCancellation + noiseSuppression.
   */
  nearField?: boolean;
};

export type MicAmplitudeControls = {
  /** 0–1 smoothed microphone level (throttled React snapshot, ~15 Hz). */
  amplitude: number;
  /** Live level for the render loop — does not trigger React updates. */
  amplitudeRef: MutableRefObject<number>;
  active: boolean;
  error: string | null;
  start: (opts?: MicStartOptions) => Promise<void>;
  stop: () => void;
};

/**
 * Web Audio AnalyserNode → smoothed amplitude for the Neural Core.
 * When inactive, amplitude stays at 0 (no media stream, no RAF loop).
 */
export function useMicAmplitude(): MicAmplitudeControls {
  const [amplitude, setAmplitude] = useState(0);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const smoothRef = useRef(0);
  const amplitudeRef = useRef(0);
  const lastPublishMs = useRef(0);
  const nearFieldRef = useRef(false);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void ctxRef.current?.close();
    ctxRef.current = null;
    analyserRef.current = null;
    smoothRef.current = 0;
    amplitudeRef.current = 0;
    lastPublishMs.current = 0;
    nearFieldRef.current = false;
    setAmplitude(0);
    setActive(false);
  }, []);

  const start = useCallback(
    async (opts?: MicStartOptions) => {
      setError(null);
      const nearField = Boolean(opts?.nearField);
      // Reuse stream when mode unchanged to avoid permission flicker mid-turn.
      if (streamRef.current && nearFieldRef.current === nearField) {
        return;
      }
      stop();
      nearFieldRef.current = nearField;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            // Near-field barge watch: no AGC so far voices stay quiet.
            autoGainControl: !nearField,
          },
          video: false,
        });
        const ctx = new AudioContext();
        const source = ctx.createMediaStreamSource(stream);
        const highpass = ctx.createBiquadFilter();
        highpass.type = 'highpass';
        highpass.frequency.value = nearField ? 120 : 85;
        highpass.Q.value = 0.7;
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.75;
        source.connect(highpass);
        highpass.connect(analyser);

        streamRef.current = stream;
        ctxRef.current = ctx;
        analyserRef.current = analyser;
        setActive(true);

        const data = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          const a = analyserRef.current;
          if (!a) return;
          a.getByteFrequencyData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i++) sum += data[i];
          const raw = Math.min(1, sum / data.length / 90);
          smoothRef.current = smoothRef.current * 0.7 + raw * 0.3;
          amplitudeRef.current = smoothRef.current;
          const now = performance.now();
          if (shouldPublishAmplitude(now, lastPublishMs.current)) {
            lastPublishMs.current = now;
            setAmplitude(smoothRef.current);
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch (err) {
        const message =
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Microphone permission denied.'
            : 'Could not access the microphone.';
        setError(message);
        stop();
      }
    },
    [stop],
  );

  useEffect(() => () => stop(), [stop]);

  return { amplitude, amplitudeRef, active, error, start, stop };
}
