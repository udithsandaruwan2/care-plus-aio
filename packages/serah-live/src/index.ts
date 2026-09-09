/** Shared Gemini Live bridge client for apps/web + Agent present UI. */

export type LiveUiLanguage = 'English' | 'Tamil' | 'Sinhala';

export type LiveMatchPayload = {
  request_id?: number;
  latency_ms?: number;
  query?: string;
  emergency?: boolean;
  results?: Array<{
    caregiver_id?: number;
    rank?: number;
    score?: number;
    display_name?: string;
    specialties?: string[];
    distance_m?: number | null;
    explanation?: string;
    trust_score?: number | null;
  }>;
} | null;

export type LiveServerMessage =
  | { type: 'live.ready'; model: string; voice?: string; ui_language?: string }
  | { type: 'live.unavailable'; reason: string }
  | { type: 'live.audio'; data: string; mime?: string }
  | { type: 'live.input_transcript'; text: string; final?: boolean }
  | { type: 'live.output_transcript'; text: string; final?: boolean; from_tool?: boolean }
  | { type: 'live.tool'; name: string; status: 'running' | 'done'; route?: string }
  | { type: 'live.match'; payload: LiveMatchPayload; cleared?: boolean }
  | { type: 'live.error'; message: string }
  | { type: 'live.closed' };

export type LiveClientHandlers = {
  onReady?: (info: { model: string; voice?: string }) => void;
  onUnavailable?: (reason: string) => void;
  onInputTranscript?: (text: string, final: boolean) => void;
  onOutputTranscript?: (text: string, final: boolean) => void;
  onTool?: (name: string, status: 'running' | 'done', route?: string) => void;
  onMatch?: (payload: LiveMatchPayload, cleared?: boolean) => void;
  onSpeaking?: (speaking: boolean) => void;
  onError?: (message: string) => void;
  onClosed?: () => void;
};

export type SerahLiveSession = {
  ready: boolean;
  start: (opts?: { uiLanguage?: LiveUiLanguage; voice?: 'female' | 'male' }) => Promise<boolean>;
  stop: () => void;
  interrupt: () => void;
  sendText: (text: string) => void;
  /** Start mic PCM capture + streaming. Returns false if mic denied / unsupported. */
  startMic: () => Promise<boolean>;
  stopMic: () => void;
};

function wsBaseFromApi(apiBase: string): string {
  try {
    if (apiBase.startsWith('/')) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${window.location.host}`;
    }
    const u = new URL(apiBase);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    u.pathname = '';
    u.search = '';
    u.hash = '';
    return u.toString().replace(/\/$/, '');
  } catch {
    return 'ws://127.0.0.1:8000';
  }
}

function decodeBase64Pcm(b64: string): Int16Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

/** Play 24 kHz mono s16le PCM via Web Audio. */
class PcmPlayer {
  private ctx: AudioContext | null = null;
  private nextTime = 0;
  private active = 0;
  private onSpeaking: ((v: boolean) => void) | undefined;

  constructor(onSpeaking?: (v: boolean) => void) {
    this.onSpeaking = onSpeaking;
  }

  enqueue(pcm: Int16Array, sampleRate = 24000) {
    if (!pcm.length) return;
    if (!this.ctx) {
      this.ctx = new AudioContext({ sampleRate });
      this.nextTime = this.ctx.currentTime;
    }
    const ctx = this.ctx;
    const f32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) f32[i] = (pcm[i] ?? 0) / 32768;
    const buf = ctx.createBuffer(1, f32.length, sampleRate);
    buf.copyToChannel(f32, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    const startAt = Math.max(ctx.currentTime, this.nextTime);
    src.start(startAt);
    this.nextTime = startAt + buf.duration;
    this.active += 1;
    this.onSpeaking?.(true);
    src.onended = () => {
      this.active = Math.max(0, this.active - 1);
      if (this.active === 0) this.onSpeaking?.(false);
    };
  }

  stop() {
    try {
      void this.ctx?.close();
    } catch {
      /* ignore */
    }
    this.ctx = null;
    this.nextTime = 0;
    this.active = 0;
    this.onSpeaking?.(false);
  }
}

async function openMicPcmStream(
  onChunk: (pcm: Int16Array) => void,
): Promise<{ stop: () => void } | null> {
  if (!navigator.mediaDevices?.getUserMedia) return null;
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  const ctx = new AudioContext({ sampleRate: 16000 });
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  processor.onaudioprocess = (ev) => {
    const input = ev.inputBuffer.getChannelData(0);
    const pcm = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i] ?? 0));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    onChunk(pcm);
  };
  source.connect(processor);
  processor.connect(ctx.destination);
  return {
    stop: () => {
      try {
        processor.disconnect();
        source.disconnect();
        void ctx.close();
        stream.getTracks().forEach((t) => t.stop());
      } catch {
        /* ignore */
      }
    },
  };
}

function pcmToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i] ?? 0);
  return btoa(binary);
}

export type CreateSerahLiveOptions = {
  /** API base like http://127.0.0.1:8000/api/v1 or /api/v1 */
  apiBaseUrl: string;
  /** Optional WS origin override (e.g. ws://127.0.0.1:8000) */
  wsBaseUrl?: string;
  getAccessToken: () => string | null;
  getUserId: () => number | null;
  handlers?: LiveClientHandlers;
};

/**
 * Create a Live bridge session. Call `start()` after consent; use `startMic()` to stream.
 */
export function createSerahLiveSession(opts: CreateSerahLiveOptions): SerahLiveSession {
  let ws: WebSocket | null = null;
  let ready = false;
  let micStop: (() => void) | null = null;
  const player = new PcmPlayer(opts.handlers?.onSpeaking);
  const h = opts.handlers || {};

  const sendJson = (payload: Record<string, unknown>) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  };

  const stop = () => {
    micStop?.();
    micStop = null;
    player.stop();
    if (ws) {
      try {
        sendJson({ type: 'live.end' });
        ws.close();
      } catch {
        /* ignore */
      }
      ws = null;
    }
    ready = false;
  };

  const start = async (startOpts?: {
    uiLanguage?: LiveUiLanguage;
    voice?: 'female' | 'male';
  }): Promise<boolean> => {
    stop();
    const token = opts.getAccessToken();
    const userId = opts.getUserId();
    if (!token || !userId) {
      h.onUnavailable?.('Not authenticated');
      return false;
    }
    const base = opts.wsBaseUrl || wsBaseFromApi(opts.apiBaseUrl);
    const url = `${base.replace(/\/$/, '')}/ws/voice/live/${userId}/?token=${encodeURIComponent(token)}`;

    return await new Promise<boolean>((resolve) => {
      let settled = false;
      const finish = (ok: boolean) => {
        if (settled) return;
        settled = true;
        resolve(ok);
      };
      try {
        ws = new WebSocket(url);
      } catch (err) {
        h.onUnavailable?.(err instanceof Error ? err.message : 'WebSocket failed');
        finish(false);
        return;
      }
      const timer = window.setTimeout(() => {
        h.onUnavailable?.('Live connect timeout');
        stop();
        finish(false);
      }, 12_000);

      ws.onmessage = (ev) => {
        let msg: LiveServerMessage;
        try {
          msg = JSON.parse(String(ev.data)) as LiveServerMessage;
        } catch {
          return;
        }
        switch (msg.type) {
          case 'live.ready':
            ready = true;
            window.clearTimeout(timer);
            h.onReady?.({ model: msg.model, voice: msg.voice });
            finish(true);
            break;
          case 'live.unavailable':
            window.clearTimeout(timer);
            h.onUnavailable?.(msg.reason);
            finish(false);
            break;
          case 'live.audio':
            player.enqueue(decodeBase64Pcm(msg.data), 24000);
            break;
          case 'live.input_transcript':
            h.onInputTranscript?.(msg.text, Boolean(msg.final));
            break;
          case 'live.output_transcript':
            h.onOutputTranscript?.(msg.text, Boolean(msg.final));
            break;
          case 'live.tool':
            h.onTool?.(msg.name, msg.status, msg.route);
            break;
          case 'live.match':
            h.onMatch?.(msg.payload ?? null, msg.cleared);
            break;
          case 'live.error':
            h.onError?.(msg.message);
            break;
          case 'live.closed':
            ready = false;
            h.onClosed?.();
            break;
          default:
            break;
        }
      };
      ws.onopen = () => {
        sendJson({
          type: 'live.start',
          ui_language: startOpts?.uiLanguage || 'English',
          voice: startOpts?.voice || 'female',
        });
      };
      ws.onerror = () => {
        window.clearTimeout(timer);
        h.onUnavailable?.('Live WebSocket error');
        finish(false);
      };
      ws.onclose = () => {
        ready = false;
        if (!settled) {
          window.clearTimeout(timer);
          finish(false);
        }
        h.onClosed?.();
      };
    });
  };

  return {
    get ready() {
      return ready;
    },
    start,
    stop,
    interrupt: () => {
      player.stop();
      sendJson({ type: 'live.interrupt' });
    },
    sendText: (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      sendJson({ type: 'live.text', text: trimmed });
    },
    startMic: async () => {
      micStop?.();
      const handle = await openMicPcmStream((pcm) => {
        sendJson({ type: 'live.audio', data: pcmToBase64(pcm) });
      });
      if (!handle) return false;
      micStop = handle.stop;
      return true;
    },
    stopMic: () => {
      micStop?.();
      micStop = null;
    },
  };
}
