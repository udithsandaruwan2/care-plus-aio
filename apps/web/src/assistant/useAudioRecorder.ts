import { useCallback, useRef } from 'react';

const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

/**
 * Records mic audio in parallel with Web Speech captions.
 * Prefer this blob for server ASR (Sinhala/Tamil) — browser STT is often English-only.
 *
 * Uses browser noise suppression plus a light high-pass (~85 Hz) so low rumble /
 * fan noise is attenuated before MediaRecorder.
 */
export function useAudioRecorder() {
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);

  const teardownGraph = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void ctxRef.current?.close();
    ctxRef.current = null;
    mediaRef.current = null;
  };

  const start = useCallback(async () => {
    chunksRef.current = [];
    teardownGraph();

    const raw = await navigator.mediaDevices.getUserMedia({
      audio: MIC_CONSTRAINTS,
      video: false,
    });
    streamRef.current = raw;

    const ctx = new AudioContext();
    ctxRef.current = ctx;
    const source = ctx.createMediaStreamSource(raw);
    const highpass = ctx.createBiquadFilter();
    highpass.type = 'highpass';
    highpass.frequency.value = 85;
    highpass.Q.value = 0.7;
    const dest = ctx.createMediaStreamDestination();
    source.connect(highpass);
    highpass.connect(dest);

    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';
    const rec = new MediaRecorder(dest.stream, { mimeType: mime });
    rec.ondataavailable = (ev) => {
      if (ev.data.size > 0) chunksRef.current.push(ev.data);
    };
    mediaRef.current = rec;
    // Timeslice keeps chunks flowing; critical for short utterances.
    rec.start(200);
  }, []);

  const stop = useCallback(async (): Promise<Blob | null> => {
    const rec = mediaRef.current;
    if (!rec || rec.state === 'inactive') {
      teardownGraph();
      return null;
    }
    const blob = await new Promise<Blob | null>((resolve) => {
      rec.onstop = () => {
        const parts = chunksRef.current;
        resolve(parts.length ? new Blob(parts, { type: rec.mimeType || 'audio/webm' }) : null);
      };
      // Flush the current buffer before stop so short speech isn't lost.
      try {
        if (rec.state === 'recording') rec.requestData();
      } catch {
        /* ignore */
      }
      rec.stop();
    });
    teardownGraph();
    return blob;
  }, []);

  return { start, stop };
}
