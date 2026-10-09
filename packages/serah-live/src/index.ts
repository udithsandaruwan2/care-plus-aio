/** Shared Gemini Live bridge client for apps/web + Agent present UI. */

import {
  createMicGateState,
  createOnsetQueue,
  downsampleTo16k,
  gateLiveFrame,
  suppressNoise,
  takePcmFrames,
} from './micGate';
import {
  appendPlayback,
  createPlaybackHold,
  createSpeakWatch,
  HOLD_LIMIT_MS,
  holdPlayback,
  onSourceEnd,
  onSourceStart,
  PLAYBACK_PREROLL_SEC,
  PLAYBACK_QUANTUM,
  PLAYBACK_STALL_MS,
  createPlaybackHeard,
  ECHO_TAIL_MS,
  micAfterBarge,
  micAfterPlaybackStop,
  notePlaybackPull,
  playbackStalled,
  pollSpeakingStopped,
  pullPlayback,
  releasePlayback,
  replyMicMode,
  resamplePlayback,
  shouldPlayPcm,
  TURN_IDLE_MS,
} from './playbackHold';

export { acceptCaption } from './captionGate';
export { ECHO_TAIL_MS, fallbackListenDelayMs } from './playbackHold';

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
  | { type: 'live.interrupted' }
  | { type: 'live.turn_complete' }
  | { type: 'live.resume' }
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

/** Play 24 kHz mono s16le PCM as one stream, so chunk edges do not click. */
class PcmPlayer {
  private ctx: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private clock: OscillatorNode | null = null;
  private pending = new Float32Array(0);
  private primed = false;
  private heard = createPlaybackHeard();
  private forcePartial = false;
  private stallTimer: ReturnType<typeof setTimeout> | null = null;
  private announcedAt = 0;
  private primeTimer: ReturnType<typeof setTimeout> | null = null;
  private onSpeaking: ((v: boolean) => void) | undefined;
  private watch = createSpeakWatch();
  private idleTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(onSpeaking?: (v: boolean) => void) {
    this.onSpeaking = onSpeaking;
  }

  private ensureGraph(sampleRate: number) {
    if (this.ctx) return;
    try {
      this.ctx = new AudioContext({ sampleRate });
    } catch {
      this.ctx = new AudioContext();
    }
    const ctx = this.ctx;
    if (ctx.state === 'suspended') void ctx.resume();
    const processor = ctx.createScriptProcessor(PLAYBACK_QUANTUM, 1, 1);
    processor.onaudioprocess = (ev) => {
      const output = ev.outputBuffer.getChannelData(0);
      const edge = Math.round((this.ctx?.sampleRate ?? 24000) * 0.005);
      const before = this.pending.length;
      const pulled = pullPlayback(
        this.pending,
        output.length,
        this.primed,
        edge,
        this.heard.lastPlayed === 0 || this.heard.afterGap,
        this.heard.lastPlayed === 0 && !this.forcePartial,
      );
      this.pending = pulled.pending;
      const held = pulled.played === 0 && before > 0 && this.primed;
      this.forcePartial = held;
      this.heard = notePlaybackPull(this.heard, pulled.played, held);
      output.set(pulled.output);
      if (!this.primed || held) return;
      if (pulled.played > 0) {
        this.watch.idleSince = null;
        if (this.idleTimer != null) {
          clearTimeout(this.idleTimer);
          this.idleTimer = null;
        }
        if (this.watch.sources === 0 && onSourceStart(this.watch)) this.onSpeaking?.(true);
        this.clearStall();
        return;
      }
      if (this.watch.sources === 0) return;
      const endedAt = performance.now();
      onSourceEnd(this.watch, endedAt);
      if (this.idleTimer != null) clearTimeout(this.idleTimer);
      this.idleTimer = setTimeout(() => {
        this.idleTimer = null;
        if (pollSpeakingStopped(this.watch, endedAt + 160)) this.onSpeaking?.(false);
      }, 160);
    };
    const clock = ctx.createOscillator();
    const muteClock = ctx.createGain();
    muteClock.gain.value = 0;
    clock.frequency.value = 1;
    clock.connect(muteClock);
    muteClock.connect(processor);
    processor.connect(ctx.destination);
    clock.start();
    this.processor = processor;
    this.clock = clock;
  }

  private clearStall() {
    if (this.stallTimer != null) clearTimeout(this.stallTimer);
    this.stallTimer = null;
  }

  private armStall() {
    this.clearStall();
    this.announcedAt = performance.now();
    this.stallTimer = setTimeout(() => {
      this.stallTimer = null;
      const elapsed = performance.now() - this.announcedAt;
      if (!playbackStalled(this.heard.lastPlayed, this.watch.announced, elapsed, PLAYBACK_STALL_MS))
        return;
      void this.ctx?.resume();
      this.watch = createSpeakWatch();
      this.onSpeaking?.(false);
    }, PLAYBACK_STALL_MS);
  }

  private primeNow() {
    if (this.primeTimer != null) {
      clearTimeout(this.primeTimer);
      this.primeTimer = null;
    }
    if (this.primed || !this.ctx) return;
    this.primed = true;
  }

  enqueue(pcm: Int16Array, sampleRate = 24000) {
    if (!pcm.length) return;
    this.ensureGraph(sampleRate);
    const ctx = this.ctx;
    if (!ctx) return;
    if (ctx.state === 'suspended') void ctx.resume();
    const f32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) f32[i] = (pcm[i] ?? 0) / 32768;
    this.pending = appendPlayback(this.pending, resamplePlayback(f32, sampleRate, ctx.sampleRate));
    if (this.idleTimer != null) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    this.watch.idleSince = null;
    if (this.watch.sources === 0 && onSourceStart(this.watch)) {
      this.heard = createPlaybackHeard();
      this.onSpeaking?.(true);
      this.armStall();
    }
    if (this.primed) return;
    const need = Math.round(ctx.sampleRate * PLAYBACK_PREROLL_SEC);
    if (this.pending.length >= need) this.primeNow();
    else if (this.primeTimer == null) {
      this.primeTimer = setTimeout(() => this.primeNow(), PLAYBACK_PREROLL_SEC * 1000);
    }
  }

  stop() {
    if (this.primeTimer != null) {
      clearTimeout(this.primeTimer);
      this.primeTimer = null;
    }
    if (this.idleTimer != null) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    this.clearStall();
    this.pending = new Float32Array(0);
    this.primed = false;
    this.forcePartial = false;
    this.watch = createSpeakWatch();
    try {
      this.clock?.stop();
      this.processor?.disconnect();
      void this.ctx?.close();
    } catch {
      /* ignore */
    }
    this.clock = null;
    this.processor = null;
    this.ctx = null;
    this.onSpeaking?.(false);
    this.heard = createPlaybackHeard();
  }

  get speaking(): boolean {
    return this.watch.announced;
  }

  /** True once this reply has actually reached the speakers. */
  get audible(): boolean {
    return this.heard.heard > 0;
  }
}

async function openMicPcmStream(
  onChunk: (pcm: Int16Array) => void,
  opts?: {
    isAssistantSpeaking?: () => boolean | 'echo-tail';
    onBarge?: () => void;
    onEchoTailOpen?: () => void;
  },
): Promise<{ stop: () => void } | null> {
  if (!navigator.mediaDevices?.getUserMedia) return null;
  const audio: MediaTrackConstraints & { voiceIsolation?: boolean } = {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    // AGC boosts inhales into the speech band. Leave it off; the gate decides.
    autoGainControl: false,
    voiceIsolation: true,
  };
  const stream = await navigator.mediaDevices.getUserMedia({ audio });
  let ctx: AudioContext;
  try {
    ctx = new AudioContext({ sampleRate: 16000 });
  } catch {
    ctx = new AudioContext();
  }
  if (ctx.state === 'suspended') void ctx.resume();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0;
  const gate = createMicGateState();
  const onset = createOnsetQueue();
  let pending = new Float32Array(0);
  const inputRate = ctx.sampleRate || 16000;
  const wireFrame = 2048;
  processor.onaudioprocess = (ev) => {
    const input = ev.inputBuffer.getChannelData(0);
    const at16k = downsampleTo16k(input, inputRate);
    const taken = takePcmFrames(pending, at16k, wireFrame);
    pending = taken.pending;
    const speaking = opts?.isAssistantSpeaking?.() ?? false;
    for (const frame of taken.frames) {
      const emit = gateLiveFrame(frame, speaking, gate, onset);
      if (emit.barge) opts?.onBarge?.();
      else if (emit.echoTailOpen) opts?.onEchoTailOpen?.();
      // Held consonants send nothing yet. A breath, or a consonant that never
      // becomes a word, is silence so the model can still hear the end of a turn.
      // While she talks, send nothing at all.
      if (emit.silenceSamples > 0) onChunk(new Int16Array(emit.silenceSamples));
      for (const piece of emit.audio) {
        const memory = { x: gate.hpX, y: gate.hpY };
        const cleaned = suppressNoise(piece, gate.noiseFloor, memory);
        gate.hpX = memory.x;
        gate.hpY = memory.y;
        const pcm = new Int16Array(cleaned.length);
        for (let i = 0; i < cleaned.length; i++) {
          const s = Math.max(-1, Math.min(1, cleaned[i] ?? 0));
          pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        onChunk(pcm);
      }
    }
  };
  // The gate needs energy under 70 Hz to tell an inhale from a consonant.
  // High-passing here would hide that rumble and let the breath start the next word.
  // Frames we do send are high-passed inside suppressNoise.
  source.connect(processor);
  // ScriptProcessor only runs while connected. Gain 0 keeps the mic off the speakers.
  processor.connect(mute);
  mute.connect(ctx.destination);
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
  let echoTailUntil = 0;
  let userHasFloor = false;
  let turnOpen = false;
  let gapTimer: ReturnType<typeof setTimeout> | null = null;
  const h = opts.handlers || {};

  const clearGapTimer = () => {
    if (gapTimer != null) clearTimeout(gapTimer);
    gapTimer = null;
  };

  const armEchoTail = () => {
    if (!userHasFloor) echoTailUntil = performance.now() + ECHO_TAIL_MS;
  };

  const applyBarge = () => {
    const next = micAfterBarge(performance.now());
    userHasFloor = next.userHasFloor;
    turnOpen = next.turnOpen;
    echoTailUntil = next.echoTailUntil;
    clearGapTimer();
  };

  const player = new PcmPlayer((speaking) => {
    if (speaking) {
      userHasFloor = false;
      turnOpen = true;
      echoTailUntil = 0;
      clearGapTimer();
      h.onSpeaking?.(true);
      return;
    }
    const after = micAfterPlaybackStop({
      userHasFloor,
      turnOpen,
      audible: player.audible,
    });
    if (after === 'floor') {
      turnOpen = false;
      clearGapTimer();
      h.onSpeaking?.(false);
      return;
    }
    // A short gap between chunks is not the end of the reply. Opening the mic
    // here would send her own voice back into the model. A reply that never
    // played does not get that hold: nothing came out of the speakers.
    if (after === 'gap') {
      clearGapTimer();
      gapTimer = setTimeout(() => {
        gapTimer = null;
        if (player.speaking || userHasFloor) return;
        turnOpen = false;
        armEchoTail();
        h.onSpeaking?.(false);
      }, TURN_IDLE_MS);
      return;
    }
    turnOpen = false;
    clearGapTimer();
    if (after === 'tail') armEchoTail();
    h.onSpeaking?.(false);
  });
  const playback = createPlaybackHold();
  let holdTimer: ReturnType<typeof setTimeout> | null = null;

  const sendJson = (payload: Record<string, unknown>) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  };

  const armHold = () => {
    holdPlayback(playback);
    if (holdTimer != null) clearTimeout(holdTimer);
    holdTimer = setTimeout(() => {
      holdTimer = null;
      releasePlayback(playback);
    }, HOLD_LIMIT_MS);
  };

  const liftHold = () => {
    if (holdTimer != null) clearTimeout(holdTimer);
    holdTimer = null;
    releasePlayback(playback);
  };

  const stop = () => {
    micStop?.();
    micStop = null;
    turnOpen = false;
    clearGapTimer();
    liftHold();
    player.stop();
    clearGapTimer();
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
            if (shouldPlayPcm(playback)) player.enqueue(decodeBase64Pcm(msg.data), 24000);
            break;
          case 'live.interrupted':
            turnOpen = false;
            clearGapTimer();
            armHold();
            if (!userHasFloor) armEchoTail();
            player.stop();
            break;
          case 'live.turn_complete':
            turnOpen = false;
            clearGapTimer();
            if (!player.speaking && !userHasFloor) {
              armEchoTail();
              h.onSpeaking?.(false);
            }
            break;
          case 'live.resume':
            liftHold();
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
      applyBarge();
      armHold();
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
      const handle = await openMicPcmStream(
        (pcm) => {
          sendJson({ type: 'live.audio', data: pcmToBase64(pcm) });
        },
        {
          isAssistantSpeaking: () =>
            replyMicMode(userHasFloor, player.speaking, turnOpen, performance.now(), echoTailUntil),
          onBarge: () => {
            applyBarge();
            armHold();
            player.stop();
            sendJson({ type: 'live.interrupt' });
          },
          onEchoTailOpen: () => {
            userHasFloor = true;
            turnOpen = false;
            clearGapTimer();
          },
        },
      );
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
