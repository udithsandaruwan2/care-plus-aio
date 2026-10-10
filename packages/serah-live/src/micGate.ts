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
  /** Voiced hops that continue across a frame boundary. A short word often does. */
  voicedRun: number;
  /** Near voiced hops while she is speaking. Same carry, used for barge-in. */
  nearRun: number;
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
    voicedRun: 0,
    nearRun: 0,
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
  if (!assistant) {
    if (state.wasSpeaking) state.nearRun = 0;
    state.wasSpeaking = false;
    state.speakBuffers = 0;
  } else if (!state.wasSpeaking) {
    state.wasSpeaking = true;
    state.speakBuffers = 0;
    state.voicedRun = 0;
  }

  const training = assistant && !echoTail && state.speakBuffers < MIC_GATE.echoTrainBuffers;
  let consonants = 0;
  let loudConsonants = 0;
  let rumbleHops = 0;
  let messyHops = 0;
  let voiceOpened = false;
  let nearOpened = false;

  for (let offset = 0; offset + hop <= samples.length; offset += hop) {
    const hopInfo = analyzeHop(samples, offset, hop);
    if (assistant) {
      const margin = Math.max(MIC_GATE.bargeRms, state.echoFloor * MIC_GATE.echoMargin);
      const userLevel = hopInfo.voiced && hopInfo.rms >= MIC_GATE.bargeRms;
      const nearHop = !training && hopInfo.voiced && hopInfo.rms >= margin;
      // The consonant that starts the word is the user. Folding it into the
      // echo floor makes the vowel that follows look too quiet to barge.
      const userConsonant = !training && hopInfo.consonant && hopInfo.rms >= margin;
      if (nearHop) {
        state.nearRun += 1;
        if (state.nearRun >= MIC_GATE.speechHops) nearOpened = true;
      } else {
        state.nearRun = 0;
        if (echoTail && userConsonant) loudConsonants += 1;
        else if (!userLevel && !userConsonant) {
          // A voice already loud enough to be the user must not become the echo
          // floor. Otherwise the training buffers swallow the barge.
          state.echoFloor = state.echoFloor * 0.82 + hopInfo.rms * 0.18;
        }
      }
    } else if (hopInfo.voiced) {
      state.voicedRun += 1;
      if (state.voicedRun >= MIC_GATE.speechHops) voiceOpened = true;
    } else {
      state.voicedRun = 0;
      if (hopInfo.consonant) consonants += 1;
      else {
        // An inhale is energy that is not a consonant. A short coda is not.
        if (hopInfo.rumble) rumbleHops += 1;
        else if (hopInfo.rms >= MIC_GATE.silenceRms) messyHops += 1;
        if (hopInfo.rms < MIC_GATE.silenceRms * 4) {
          state.noiseFloor = state.noiseFloor * 0.8 + hopInfo.rms * 0.2;
        }
      }
    }
  }

  if (assistant) {
    if (!echoTail) state.speakBuffers += 1;
    state.quietBuffers = 0;
    if (nearOpened) {
      state.inUtterance = true;
      return echoTail ? 'send' : 'barge';
    }
    // The vowel already opened the turn. A short consonant is still part of
    // that word. A quiet frame is not, so her ring does not keep the turn open.
    if (echoTail && state.inUtterance && loudConsonants > 0) {
      return 'send';
    }
    state.inUtterance = false;
    return 'drop';
  }

  if (voiceOpened) {
    state.inUtterance = true;
    state.quietBuffers = 0;
    return 'send';
  }
  // Three consonant hops are still speech. A shorter coda is speech only when
  // every other hop is silence. An inhale leaves messy energy and stays dropped.
  const cleanCoda = consonants > 0 && rumbleHops === 0 && messyHops === 0;
  if (state.inUtterance && (consonants >= MIC_GATE.speechHops || cleanCoda)) {
    state.quietBuffers = 0;
    return 'send';
  }
  if (state.inUtterance) {
    state.quietBuffers += 1;
    if (state.quietBuffers > MIC_GATE.hangoverBuffers) state.inUtterance = false;
  }
  return 'drop';
}

export type OnsetQueue = {
  frames: Float32Array[];
  breath: boolean;
  /** Near hops from the previous frame. Bleed in that frame is already zeroed. */
  partial: Float32Array | null;
  /** Frames of her voice since the held consonant. Her voice is not the end of the word. */
  gaps: number;
};

export function createOnsetQueue(): OnsetQueue {
  return { frames: [], breath: false, partial: null, gaps: 0 };
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
 * Hops that are not the user's near voice become silence.
 * A partial barge frame can then be sent later without replaying her.
 */
function speechKeptFrame(
  frame: Float32Array,
  assistantSpeaking: MicListenMode,
  echoFloor: number,
): Float32Array | null {
  const echoTail = assistantSpeaking === 'echo-tail';
  const hop = MIC_GATE.hop;
  const out = new Float32Array(frame.length);
  let kept = 0;
  let floor = echoFloor;
  let heardVoiced = false;
  for (let offset = 0; offset + hop <= frame.length; offset += hop) {
    const info = analyzeHop(frame, offset, hop);
    const margin = Math.max(MIC_GATE.bargeRms, floor * MIC_GATE.echoMargin);
    const voicedNear = info.voiced && info.rms >= margin;
    const loudConsonant = info.consonant && info.rms >= margin;
    // The consonant that starts the word shares this frame with the vowel.
    // A loud hop after the vowel is not that consonant.
    const opening = loudConsonant && !heardVoiced;
    const take = voicedNear || (echoTail && loudConsonant) || (!echoTail && opening);
    if (take) {
      for (let i = 0; i < hop; i++) out[offset + i] = frame[offset + i] ?? 0;
      kept += 1;
    }
    if (voicedNear) heardVoiced = true;
    // Same floor update as pushMicBuffer. A later loud hop must not erase
    // a nearer hop that already cleared the floor it was measured against.
    // A consonant above the margin is the user and must not raise it either.
    if (!voicedNear && !loudConsonant) {
      const userLevel = info.voiced && info.rms >= MIC_GATE.bargeRms;
      if (!userLevel) floor = floor * 0.82 + info.rms * 0.18;
    }
  }
  return kept > 0 ? out : null;
}

/**
 * Loud consonant hops above the echo floor, before a vowel confirms the barge.
 * Rumble is an inhale and is not stored. Hops under the floor are her voice.
 */
function bargeOnsetFrame(
  frame: Float32Array,
  assistantSpeaking: MicListenMode,
  echoFloor: number,
): Float32Array | null {
  void assistantSpeaking;
  const hop = MIC_GATE.hop;
  const out = new Float32Array(frame.length);
  let kept = 0;
  let rumble = 0;
  let floor = echoFloor;
  for (let offset = 0; offset + hop <= frame.length; offset += hop) {
    const info = analyzeHop(frame, offset, hop);
    if (info.rumble) rumble += 1;
    const margin = Math.max(MIC_GATE.bargeRms, floor * MIC_GATE.echoMargin);
    const voicedNear = info.voiced && info.rms >= margin;
    const loudConsonant = info.consonant && info.rms >= margin;
    if (loudConsonant) {
      for (let i = 0; i < hop; i++) out[offset + i] = frame[offset + i] ?? 0;
      kept += 1;
    }
    if (!voicedNear && !loudConsonant) {
      const userLevel = info.voiced && info.rms >= MIC_GATE.bargeRms;
      if (!userLevel) floor = floor * 0.82 + info.rms * 0.18;
    }
  }
  if (rumble > 0 || kept === 0) return null;
  return out;
}

/** Her vowel in the gap. A breath is mostly not periodic, so it does not qualify. */
function frameIsHerVoice(frame: Float32Array): boolean {
  const hop = MIC_GATE.hop;
  let hops = 0;
  let voiced = 0;
  for (let offset = 0; offset + hop <= frame.length; offset += hop) {
    hops += 1;
    const info = analyzeHop(frame, offset, hop);
    if (info.rumble) return false;
    if (info.voiced) voiced += 1;
  }
  return hops > 0 && voiced * 2 > hops;
}

/**
 * Same decisions as `pushMicBuffer`, plus the consonant that started the word.
 * While she is talking, only the nearer hops are held. The rest of that frame
 * is her voice and must not be replayed when the word continues.
 */
export function gateLiveFrame(
  frame: Float32Array,
  assistantSpeaking: MicListenMode,
  state: MicGateState,
  onset: OnsetQueue,
): LiveMicEmit {
  const speaking = assistantSpeaking === true || assistantSpeaking === 'echo-tail';
  if (speaking) {
    // The first frame of her turn drops a consonant the user had not finished.
    // Later frames keep a loud consonant until the vowel that barges.
    if (!state.wasSpeaking) {
      onset.frames.length = 0;
      onset.breath = false;
      onset.gaps = 0;
    }
  } else {
    // The consonant was already masked to the near voice. Dropping it here
    // cuts the word off when the echo tail ends before the vowel arrives.
    if (state.wasSpeaking) onset.breath = false;
    onset.partial = null;
  }

  const echoFloor = state.echoFloor;
  const nearBefore = state.nearRun;
  const decision = pushMicBuffer(frame, assistantSpeaking, state);
  if (decision === 'drop') {
    if (speaking) {
      if (state.nearRun > 0) {
        onset.partial = speechKeptFrame(frame, assistantSpeaking, echoFloor);
        onset.gaps = 0;
        return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
      }
      // The first buffers learn her level. A consonant there is still her voice.
      const training = assistantSpeaking === true && state.speakBuffers <= MIC_GATE.echoTrainBuffers;
      if (!training && !onset.breath) {
        const lead = bargeOnsetFrame(frame, assistantSpeaking, echoFloor);
        if (lead) {
          onset.partial = null;
          if (onset.frames.length >= MIC_GATE.onsetFrames) {
            onset.frames.length = 0;
            onset.breath = true;
            onset.gaps = 0;
            return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
          }
          onset.frames.push(lead);
          onset.gaps = 0;
          return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
        }
        // Her vowel fills the gap inside the word. It must not erase the hops
        // already counted, and an inhale must not keep them.
        if ((onset.frames.length > 0 || onset.partial) && frameIsHerVoice(frame)) {
          if (onset.partial && nearBefore > 0) state.nearRun = nearBefore;
          onset.gaps += 1;
          if (onset.gaps > MIC_GATE.onsetFrames) {
            onset.frames.length = 0;
            onset.partial = null;
            onset.gaps = 0;
            state.nearRun = 0;
          }
          return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
        }
      }
      onset.frames.length = 0;
      onset.partial = null;
      onset.gaps = 0;
      return { audio: [], silenceSamples: 0, barge: false, echoTailOpen: false };
    } else if (isOnsetFrame(frame)) {
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

  let audio: Float32Array[];
  if (speaking) {
    // Floor at the start of the frame. Each hop is judged as it was heard.
    // Never fall back to the raw frame: the rest of it is her voice.
    const kept = speechKeptFrame(frame, assistantSpeaking, echoFloor);
    audio = [];
    if (!onset.breath) {
      for (const lead of onset.frames) audio.push(lead);
    }
    if (onset.partial) audio.push(onset.partial);
    if (kept) audio.push(kept);
    onset.partial = null;
  } else {
    audio = onset.breath ? [frame] : onset.frames.concat(frame);
  }
  onset.frames.length = 0;
  onset.breath = false;
  const heard = audio.length > 0;
  return {
    audio,
    silenceSamples: 0,
    barge: decision === 'barge' && heard,
    echoTailOpen: decision === 'send' && assistantSpeaking === 'echo-tail' && heard,
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

/**
 * Samples per Live API send. 512 samples at 16 kHz is 32 ms.
 * The model does not treat a barge as an interruption when a chunk is longer
 * than about 40 ms. The breath gate still sees a full 2048-sample frame first.
 */
export const LIVE_PCM_SAMPLES = 512;

export function chunkLivePcm(pcm: Int16Array, size = LIVE_PCM_SAMPLES): Int16Array[] {
  if (pcm.length === 0 || size <= 0) return [];
  if (pcm.length <= size) return [pcm];
  const out: Int16Array[] = [];
  for (let offset = 0; offset < pcm.length; offset += size) {
    out.push(pcm.subarray(offset, Math.min(pcm.length, offset + size)));
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

/**
 * She has taken the speaker. Commit the user's audio once.
 * Do not commit when the echo tail opens: the barge words are still arriving.
 */
/**
 * One mic callback can hold two frames. The vowel barges on the first, and the
 * consonant is still in the second. That second frame has to use the echo tail,
 * or it is gated as her voice and the rest of the word is dropped.
 */
export function modeAfterBarge(barged: boolean, mode: MicListenMode): MicListenMode {
  if (barged && mode === true) return 'echo-tail';
  return mode;
}

/**
 * The echo-tail timer can expire while a word is still held.
 * Opening the mic then treats her ring as the rest of that word.
 * Stay in the tail until the hold is confirmed or cleared.
 * A word she is not part of stays on the open mic, or a quiet vowel is lost.
 */
export function modeWhileHolding(
  mode: MicListenMode,
  previous: MicListenMode | null,
  onset: OnsetQueue,
  nearRun: number,
): MicListenMode {
  if (mode !== false) return mode;
  const wasHers = previous === true || previous === 'echo-tail';
  if (!wasHers) return mode;
  // A finished vowel leaves nearRun high. Holding the tail for that drops the
  // next quiet word. Only an unfinished run still needs the tail.
  const unfinished = nearRun > 0 && nearRun < MIC_GATE.speechHops;
  if (onset.partial || onset.frames.length > 0 || unfinished) return 'echo-tail';
  return mode;
}

export function shouldFlushMicStream(
  previous: MicListenMode | null,
  next: MicListenMode,
): boolean {
  return previous !== null && previous !== true && next === true;
}

/**
 * Samples waiting for a full frame were captured in one mic mode.
 * The open mic would send her voice in that tail, so a change onto it
 * discards the tail. The echo tail still strips her, and dropping the
 * samples there cuts off the start of the barge.
 */
export function pendingForMode(
  pending: Float32Array,
  previous: MicListenMode | null,
  next: MicListenMode,
): Float32Array {
  if (previous === true && next === 'echo-tail') return pending;
  if (previous !== null && previous !== next) return new Float32Array(0);
  return pending;
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
