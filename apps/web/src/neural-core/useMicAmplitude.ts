import { useCallback, useEffect, useRef, useState } from 'react';

export type MicAmplitudeControls = {
  /** 0–1 smoothed microphone level */
  amplitude: number;
  active: boolean;
  error: string | null;
  start: () => Promise<void>;
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

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void ctxRef.current?.close();
    ctxRef.current = null;
    analyserRef.current = null;
    smoothRef.current = 0;
    setAmplitude(0);
    setActive(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    stop();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);

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
        setAmplitude(smoothRef.current);
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
  }, [stop]);

  useEffect(() => () => stop(), [stop]);

  return { amplitude, active, error, start, stop };
}
