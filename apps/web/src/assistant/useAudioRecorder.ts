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
 * Browser noiseSuppression / echoCancellation / AGC only — avoid routing through
 * AudioContext→MediaStreamDestination (unstable MediaRecorder behaviour in Chrome).
 */
export function useAudioRecorder() {
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const start = useCallback(async () => {
    chunksRef.current = [];
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRef.current = null;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: MIC_CONSTRAINTS,
      video: false,
    });
    streamRef.current = stream;
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';
    const rec = new MediaRecorder(stream, { mimeType: mime });
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
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      mediaRef.current = null;
      return null;
    }
    const blob = await new Promise<Blob | null>((resolve) => {
      rec.onstop = () => {
        const parts = chunksRef.current;
        resolve(parts.length ? new Blob(parts, { type: rec.mimeType || 'audio/webm' }) : null);
      };
      try {
        if (rec.state === 'recording') rec.requestData();
      } catch {
        /* ignore */
      }
      rec.stop();
    });
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRef.current = null;
    return blob;
  }, []);

  return { start, stop };
}
