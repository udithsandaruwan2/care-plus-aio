/**
 * Live mic gate.
 *
 * A breath is noisy and not periodic, so level alone must not open a turn.
 * While the assistant is talking, the first moments train an echo floor and
 * only a voice well above that floor counts as barge-in.
 */

export const MIC_GATE = {
  sampleRate: 16000,
  hop: 512,
  /** Pitch search, Hz. */
  pitchMinHz: 80,
  pitchMaxHz: 400,
  /** Normalized autocorrelation above this is a voiced frame. */
  voicedPeriod: 0.42,
  /** Energy under ~70 Hz above this is inhale rumble, not a vowel. */
  rumbleRatio: 0.55,
  /** Quiet room. Frames under this never open a turn. */
  silenceRms: 0.012,
  /** Barge must also clear this absolute level. */
  bargeRms: 0.06,
  /** Near speech must be this many times the learned echo floor. */
  echoMargin: 2.4,
  /** Buffers of playback used only to learn the echo, never to barge. */
  echoTrainBuffers: 2,
  /** Voiced hops inside one buffer required to send or barge. */
  speechHops: 3,
  /** Buffers of quiet after a vowel before the utterance closes. */
  hangoverBuffers: 3,
  /** Consonant frames held until a vowel confirms they started a word. */
  onsetFrames: 2,
} as const;

export type MicGateDecision = 'drop' | 'send' | 'barge';

export type MicGateState = {
  echoFloor: number;
  noiseFloor: number;
  speakBuffers: number;
  wasSpeaking: boolean;
  /** A vowel has opened the user's turn. Consonants may follow; a breath may not. */
  inUtterance: boolean;
  quietBuffers: number;
  hpX: number;
  hpY: number;
};

export function createMicGateState(): MicGateState {
  return {
    echoFloor: 0.02,
    noiseFloor: 0.005,
    speakBuffers: 0,
    wasSpeaking: false,
    inUtterance: false,
    quietBuffers: 0,
    hpX: 0,
    hpY: 0,
  };
}

export function frameRms(samples: ArrayLike<number>): number {
  const n = samples.length;
  if (!n) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const s = samples[i] ?? 0;
    sum += s * s;
  }
  return Math.sqrt(sum / n);
}

export function zeroCrossingRate(samples: ArrayLike<number>): number {
  if (samples.length < 2) return 0;
  let crossings = 0;
  for (let i = 1; i < samples.length; i++) {
    const a = samples[i - 1] ?? 0;
    const b = samples[i] ?? 0;
    if ((a >= 0 && b < 0) || (a < 0 && b >= 0)) crossings += 1;
  }
  return crossings / (samples.length - 1);
}

/** Share of energy that survives a ~70 Hz one-pole low-pass. */
export function lowBandRatio(samples: ArrayLike<number>, sampleRate = MIC_GATE.sampleRate): number {
  const dt = 1 / sampleRate;
  const rc = 1 / (2 * Math.PI * 70);
  const alpha = dt / (rc + dt);
  let y = 0;
  let low = 0;
  let total = 0;
  for (let i = 0; i < samples.length; i++) {
    const x = samples[i] ?? 0;
    y += alpha * (x - y);
    low += y * y;
    total += x * x;
  }
  return total < 1e-8 ? 0 : low / total;
}

/** Best normalized autocorrelation in the speech-pitch lag range. */
export function periodicity(samples: ArrayLike<number>, sampleRate = MIC_GATE.sampleRate): number {
  const n = samples.length;
  if (n < 8) return 0;
  let energy = 0;
  for (let i = 0; i < n; i++) {
    const s = samples[i] ?? 0;
    energy += s * s;
  }
  if (energy < 1e-8) return 0;
  const minLag = Math.max(1, Math.round(sampleRate / MIC_GATE.pitchMaxHz));
  const maxLag = Math.min(n - 2, Math.round(sampleRate / MIC_GATE.pitchMinHz));
  let best = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let corr = 0;
    const limit = n - lag;
    for (let i = 0; i < limit; i++) corr += (samples[i] ?? 0) * (samples[i + lag] ?? 0);
    const norm = corr / energy;
    if (norm > best) best = norm;
  }
  return best;
}

export function isVoicedHop(samples: ArrayLike<number>): boolean {
  const rms = frameRms(samples);
  if (rms < MIC_GATE.silenceRms) return false;
  if (lowBandRatio(samples) >= MIC_GATE.rumbleRatio) return false;
  if (zeroCrossingRate(samples) > 0.2) return false;
  return periodicity(samples) >= MIC_GATE.voicedPeriod;
}

export type MicListenMode = boolean | 'echo-tail';

/**
 * One mic buffer (typically 4096 samples). Updates `state`.
 * `drop` means do not forward the waveform.
 * `'echo-tail'` is the speaker ring after she stops: bleed is dropped, and a
 * nearer voice is sent without counting as a barge-in.
 */
export function pushMicBuffer(
  samples: ArrayLike<number>,
  assistantSpeaking: MicListenMode,
  state: MicGateState,
): MicGateDecision {
  const echoTail = assistantSpeaking === 'echo-tail';
  const assistant = assistantSpeaking === true || echoTail;
  const hop = MIC_GATE.hop;
  let voiced = 0;
  let near = 0;
  if (!assistant) {
    state.wasSpeaking = false;
    state.speakBuffers = 0;
  } else if (!state.wasSpeaking) {
    state.wasSpeaking = true;
    state.speakBuffers = 0;
  }

  const training = assistant && !echoTail && state.speakBuffers < MIC_GATE.echoTrainBuffers;
  let consonants = 0;

  for (let offset = 0; offset + hop <= samples.length; offset += hop) {
    const hopInfo = analyzeHop(samples, offset, hop);
    if (assistant) {
      const margin = Math.max(MIC_GATE.bargeRms, state.echoFloor * MIC_GATE.echoMargin);
      const userLevel = hopInfo.voiced && hopInfo.rms >= MIC_GATE.bargeRms;
      if (!training && hopInfo.voiced && hopInfo.rms >= margin) {
        near += 1;
      } else if (!userLevel) {
        // A voice already loud enough to be the user must not become the echo
        // floor. Otherwise the training buffers swallow the barge.
        state.echoFloor = state.echoFloor * 0.82 + hopInfo.rms * 0.18;
      }
      if (hopInfo.voiced) voiced += 1;
    } else if (hopInfo.voiced) {
      voiced += 1;
    } else if (hopInfo.consonant) {
      consonants += 1;
    } else if (hopInfo.rms < MIC_GATE.silenceRms * 4) {
      state.noiseFloor = state.noiseFloor * 0.8 + hopInfo.rms * 0.2;
    }
  }

  if (assistant) {
    if (!echoTail) state.speakBuffers += 1;
    state.quietBuffers = 0;
    if (!training && near >= MIC_GATE.speechHops) {
      state.inUtterance = true;
      return echoTail ? 'send' : 'barge';
    }
    state.inUtterance = false;
    return 'drop';
  }

  if (voiced >= MIC_GATE.speechHops) {
    state.inUtterance = true;
    state.quietBuffers = 0;
    return 'send';
  }
  if (state.inUtterance && consonants >= MIC_GATE.speechHops) {
    state.quietBuffers = 0;
    return 'send';
  }
  if (state.inUtterance) {
    state.quietBuffers += 1;
    if (state.quietBuffers > MIC_GATE.hangoverBuffers) state.inUtterance = false;
  }
  return 'drop';
}

export type OnsetQueue = { frames: Float32Array[]; breath: boolean };

export function createOnsetQueue(): OnsetQueue {
  return { frames: [], breath: false };
}

export type LiveMicEmit = {
  /** Speech to forward, oldest first. A held consonant precedes the vowel that confirmed it. */
  audio: Float32Array[];
  /** Zeros to forward when a held onset was not a word, so the turn can still end. */
  silenceSamples: number;
  barge: boolean;
  echoTailOpen: boolean;
};

/**
 * A frame worth keeping until a vowel confirms the word.
 * Any sub-70 Hz rumble rejects it, so an inhale is not stored.
 * A short mix of consonant and vowel is kept too: one 128 ms frame often holds both.
 */
export function isOnsetFrame(samples: ArrayLike<number>): boolean {
  const hop = MIC_GATE.hop;
  let consonants = 0;
  let voiced = 0;
  let rumble = 0;
  for (let offset = 0; offset + hop <= samples.length; offset += hop) {
    const info = analyzeHop(samples, offset, hop);
    if (info.voiced) voiced += 1;
    else if (info.consonant) consonants += 1;
    else if (info.rumble) rumble += 1;
  }
  if (rumble > 0) return false;
  if (consonants >= MIC_GATE.speechHops) return true;
  return voiced > 0 && consonants + voiced >= 2;
}

/**
 * Same decisions as `pushMicBuffer`, plus the consonant that started the word.
 * While she is talking, nothing is held: speaker bleed must not be replayed later.
 */
export function gateLiveFrame(
  frame: Float32Array,
  assistantSpeaking: MicListenMode,
  state: MicGateState,
  onset: OnsetQueue,
): LiveMicEmit {
  const speaking = assistantSpeaking === true || assistantSpeaking === 'echo-tail';
  if (speaking) {
    onset.frames.length = 0;
    onset.breath = false;
  }

  const decision = pushMicBuffer(frame, assistantSpeaking, state);
  if (decision === 'drop') {
    if (!speaking && isOnsetFrame(frame)) {
      if (onset.breath) {
        return { audio: [], silenceSamples: frame.length, barge: false, echoTailOpen: false };
      }
      // A consonant is short. Another noisy frame after the hold is an inhale.
      if (onset.frames.length >= MIC_GATE.onsetFrames) {
        const dumped = onset.frames.length + 1;
        onset.frames.length = 0;
        onset.breath = true;
        return {
          audio: [],
          silenceSamples: dumped * frame.length,
          barge: false,
          echoTailOpen: false,
        };
      }
      onset.frames.push(new Float32Array(frame));
      return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
    }
    const held = onset.frames.length;
    onset.frames.length = 0;
    onset.breath = false;
    return {
      audio: [],
      silenceSamples: speaking ? 0 : (held + 1) * frame.length,
      barge: false,
      echoTailOpen: false,
    };
  }

  const audio = speaking || onset.breath ? [frame] : onset.frames.concat(frame);
  onset.frames.length = 0;
  onset.breath = false;
  return {
    audio,
    silenceSamples: 0,
    barge: decision === 'barge',
    echoTailOpen: decision === 'send' && assistantSpeaking === 'echo-tail',
  };
}

function analyzeHop(
  samples: ArrayLike<number>,
  offset: number,
  length: number,
): { rms: number; voiced: boolean; consonant: boolean; rumble: boolean } {
  const hop = new Float32Array(length);
  for (let i = 0; i < length; i++) hop[i] = samples[offset + i] ?? 0;
  const rms = frameRms(hop);
  const low = lowBandRatio(hop);
  const voiced = isVoicedHop(hop);
  const consonant =
    !voiced &&
    rms >= MIC_GATE.silenceRms &&
    low < MIC_GATE.rumbleRatio &&
    zeroCrossingRate(hop) >= 0.12;
  const rumble = !voiced && !consonant && rms >= MIC_GATE.silenceRms && low >= MIC_GATE.rumbleRatio;
  return { rms, voiced, consonant, rumble };
}

export type FilterMemory = { x: number; y: number };

/** Attenuate stationary noise. A loud voiced frame keeps most of its level. */
export function suppressNoise(
  samples: ArrayLike<number>,
  noiseRms: number,
  memory?: FilterMemory,
): Float32Array {
  const out = new Float32Array(samples.length);
  const rms = frameRms(samples);
  if (rms < 1e-8) return out;
  const floor = Math.max(0, noiseRms);
  const gain = rms <= floor ? 0 : Math.min(1, 1 - (floor / rms) * 0.9);
  let prevX = memory?.x ?? 0;
  let prevY = memory?.y ?? 0;
  const a = 0.95;
  for (let i = 0; i < samples.length; i++) {
    const x = (samples[i] ?? 0) * gain;
    const y = a * (prevY + x - prevX);
    out[i] = Math.max(-1, Math.min(1, y));
    prevX = x;
    prevY = y;
  }
  if (memory) {
    memory.x = prevX;
    memory.y = prevY;
  }
  return out;
}

/** Average blocks so the live model always receives 16 kHz, whatever the device rate is. */
export function downsampleTo16k(samples: ArrayLike<number>, fromRate: number): Float32Array {
  const rate = fromRate > 0 ? fromRate : MIC_GATE.sampleRate;
  if (Math.abs(rate - MIC_GATE.sampleRate) < 1) {
    const same = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) same[i] = samples[i] ?? 0;
    return same;
  }
  const ratio = rate / MIC_GATE.sampleRate;
  const outLen = Math.max(0, Math.floor(samples.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let n = 0;
    for (let j = start; j < end; j++) {
      sum += samples[j] ?? 0;
      n += 1;
    }
    out[i] = n ? sum / n : 0;
  }
  return out;
}

/** Pull fixed 16 kHz frames out of a rolling buffer so a short device buffer can still hold a word. */
export function takePcmFrames(
  pending: Float32Array,
  incoming: ArrayLike<number>,
  frameSize: number,
): { pending: Float32Array; frames: Float32Array[] } {
  const merged = new Float32Array(pending.length + incoming.length);
  merged.set(pending, 0);
  for (let i = 0; i < incoming.length; i++) merged[pending.length + i] = incoming[i] ?? 0;
  const frames: Float32Array[] = [];
  let offset = 0;
  while (frameSize > 0 && offset + frameSize <= merged.length) {
    frames.push(merged.slice(offset, offset + frameSize));
    offset += frameSize;
  }
  return { pending: merged.slice(offset), frames };
}
