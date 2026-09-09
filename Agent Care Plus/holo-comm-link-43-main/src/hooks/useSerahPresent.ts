import { useCallback, useEffect, useRef, useState } from "react";
import type { MatchResponse, VoiceTurnIntent } from "@care-plus/api-client";
import {
  createSerahLiveSession,
  type SerahLiveSession,
} from "@care-plus/serah-live";

import { api, getAccessToken } from "@/lib/careplus-api";
import {
  ensureSerahSession,
  type BootResult,
  type SessionStatus,
} from "@/lib/serah-session";

export type SerahMode = "idle" | "listening" | "thinking" | "speaking";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export type DiagnosticLine = {
  id: string;
  text: string;
};

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getSpeechCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

function playBase64Audio(base64: string, mime: string): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: mime || "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      const done = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onended = done;
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Audio playback failed"));
      };
      void audio.play().catch(reject);
    } catch (err) {
      reject(err instanceof Error ? err : new Error("Audio decode failed"));
    }
  });
}

function speakBrowserTts(text: string, lang: string): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = lang || "en-US";
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    window.speechSynthesis.speak(utter);
  });
}

/**
 * Presentation bridge: demo session → text/mic → voiceTurn → chat + modes + MatchRail + TTS.
 */
export function useSerahPresent() {
  const [boot, setBoot] = useState<BootResult>({
    status: "booting",
    userId: null,
    message: "Linking Care Plus…",
  });
  const [mode, setMode] = useState<SerahMode>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Hi - I'm Serah from Care Plus. Say hello, or ask me to find a caregiver.",
    },
  ]);
  const [interim, setInterim] = useState("");
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [logs, setLogs] = useState<DiagnosticLine[]>([
    { id: "boot-0", text: "SYS :: Serah presentation kernel online" },
    { id: "boot-1", text: "NET :: Awaiting Care Plus uplink" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [micSupported, setMicSupported] = useState(false);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);

  const busyRef = useRef(false);
  const intentRef = useRef<VoiceTurnIntent | null>(null);
  const matchRef = useRef<MatchResponse | null>(null);
  const recRef = useRef<SpeechRecognition | null>(null);
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finalChunks = useRef<string[]>([]);
  const interimRef = useRef("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const liveRef = useRef<SerahLiveSession | null>(null);
  const liveActiveRef = useRef(false);
  const userIdRef = useRef<number | null>(null);
  const [liveActive, setLiveActive] = useState(false);

  const pushLog = useCallback((text: string) => {
    setLogs((prev) => [...prev.slice(-10), { id: uid(), text }]);
  }, []);

  useEffect(() => {
    setMicSupported(getSpeechCtor() !== null || Boolean(navigator.mediaDevices?.getUserMedia));
    let cancelled = false;
    void (async () => {
      const result = await ensureSerahSession();
      if (cancelled) return;
      setBoot(result);
      userIdRef.current = result.userId;
      if (result.status === "online") {
        pushLog(`AUTH :: ${result.message}`);
        pushLog("SEC :: AI processing consent verified");
      } else {
        pushLog(`ERR :: ${result.message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pushLog]);

  useEffect(() => {
    if (boot.status !== "online" || !boot.userId) return;
    const session = createSerahLiveSession({
      apiBaseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1",
      getAccessToken,
      getUserId: () => userIdRef.current,
      handlers: {
        onReady: ({ model }) => {
          liveActiveRef.current = true;
          setLiveActive(true);
          pushLog(`LIVE :: Gemini ${model} ready`);
        },
        onUnavailable: (reason) => {
          liveActiveRef.current = false;
          setLiveActive(false);
          pushLog(`LIVE :: unavailable — ${reason.slice(0, 80)}`);
        },
        onInputTranscript: (text, final) => {
          if (final && text.trim()) {
            setInterim("");
            setMessages((prev) => [...prev, { id: uid(), role: "user", text: text.trim() }]);
          } else {
            setInterim(text);
          }
        },
        onOutputTranscript: (text, final) => {
          if (final && text.trim()) {
            setMessages((prev) => [...prev, { id: uid(), role: "assistant", text: text.trim() }]);
          }
        },
        onTool: (_name, status) => {
          if (status === "running") {
            setMode("thinking");
            pushLog("TURN :: Serah is thinking…");
          }
        },
        onMatch: (payload, cleared) => {
          if (cleared || !payload) {
            matchRef.current = null;
            setMatch(null);
            pushLog("MATCH :: Cleared prior results");
            return;
          }
          const asMatch = payload as MatchResponse;
          matchRef.current = asMatch;
          setMatch(asMatch);
          pushLog(
            `MATCH :: VEHMF returned ${(asMatch.results || []).length} caregivers`,
          );
        },
        onSpeaking: (speaking) => {
          setMode(speaking ? "speaking" : liveActiveRef.current ? "listening" : "idle");
          if (speaking) pushLog("SYNTH :: Streaming Serah Live voice");
        },
        onError: (message) => {
          setError(message);
          pushLog(`ERR :: ${message}`);
        },
        onClosed: () => {
          liveActiveRef.current = false;
          setLiveActive(false);
          setMode((m) => (m === "listening" || m === "speaking" ? "idle" : m));
        },
      },
    });
    liveRef.current = session;
    return () => {
      session.stop();
      liveRef.current = null;
      liveActiveRef.current = false;
    };
  }, [boot.status, boot.userId, pushLog]);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const clearSilence = () => {
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current);
      silenceTimer.current = null;
    }
  };

  const stopMic = useCallback(() => {
    clearSilence();
    try {
      recRef.current?.stop();
    } catch {
      /* already stopped */
    }
  }, []);

  const playReply = useCallback(
    async (reply: string, result: Awaited<ReturnType<typeof api.voiceTurn>>) => {
      if (!reply.trim() || result.silent) {
        setMode("idle");
        return;
      }
      setMode("speaking");
      pushLog("SYNTH :: Streaming Serah voice");
      try {
        if (result.reply_audio_base64) {
          await playBase64Audio(
            result.reply_audio_base64,
            result.reply_audio_mime || "audio/mpeg",
          );
        } else if (result.audio_pending && reply.trim()) {
          const tts = await api.voiceTts({
            text: reply,
            replyLang: result.reply_lang || "en-US",
            voice: "female",
          });
          if (tts.reply_audio_base64) {
            await playBase64Audio(
              tts.reply_audio_base64,
              tts.reply_audio_mime || "audio/mpeg",
            );
          } else {
            await speakBrowserTts(reply, result.reply_lang || "en-US");
          }
        } else {
          await speakBrowserTts(reply, result.reply_lang || "en-US");
        }
      } catch {
        await speakBrowserTts(reply, result.reply_lang || "en-US");
      } finally {
        setMode("idle");
        pushLog("IDLE :: Awaiting next directive");
      }
    },
    [pushLog],
  );

  const runTurn = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;
      if (boot.status !== "online") {
        setError("Care Plus link is offline. Restart the backend and refresh.");
        return;
      }

      if (liveActiveRef.current && liveRef.current?.ready) {
        setMessages((prev) => [...prev, { id: uid(), role: "user", text: trimmed }]);
        setMode("thinking");
        liveRef.current.sendText(trimmed);
        return;
      }

      busyRef.current = true;
      setError(null);
      stopPlayback();
      setInterim("");
      setMode("thinking");
      pushLog("TURN :: Serah is thinking…");
      setMessages((prev) => [...prev, { id: uid(), role: "user", text: trimmed }]);

      try {
        const hasPrior = Boolean(matchRef.current?.results?.length);
        const result = await api.voiceTurn({
          text: trimmed,
          audio: null,
          hasPriorMatch: hasPrior,
          priorIntent: intentRef.current
            ? (intentRef.current as unknown as Record<string, unknown>)
            : null,
          priorMatch: hasPrior
            ? (matchRef.current as unknown as Record<string, unknown>)
            : null,
          uiLanguage: "English",
          voice: "female",
        });

        if (result.timings?.total_ms) {
          setLastLatencyMs(Math.round(result.timings.total_ms));
        }
        pushLog(
          `ROUTE :: ${result.route}${result.chat_source ? ` / ${result.chat_source}` : ""}`,
        );

        if (result.intent) intentRef.current = result.intent;

        if (result.clear_match) {
          matchRef.current = null;
          setMatch(null);
          pushLog("MATCH :: Cleared prior results");
        }

        if (result.match?.results?.length) {
          matchRef.current = result.match;
          setMatch(result.match);
          pushLog(
            `MATCH :: VEHMF returned ${result.match.results.length} caregivers (${Math.round(result.match.latency_ms)}ms)`,
          );
        } else if (result.route === "MATCH") {
          pushLog("MATCH :: Searching caregivers…");
        }

        const reply = result.reply?.trim() || "";
        if (reply && !result.silent) {
          setMessages((prev) => [
            ...prev,
            { id: uid(), role: "assistant", text: reply },
          ]);
        }

        await playReply(reply, result);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Voice turn failed";
        setError(message);
        pushLog(`ERR :: ${message}`);
        setMode("idle");
        setMessages((prev) => [
          ...prev,
          {
            id: uid(),
            role: "assistant",
            text: "I could not reach Care Plus just now. Please try again.",
          },
        ]);
      } finally {
        busyRef.current = false;
      }
    },
    [boot.status, playReply, pushLog, stopPlayback],
  );

  const startListening = useCallback(() => {
    if (busyRef.current || boot.status !== "online") return;
    stopPlayback();
    clearSilence();
    setError(null);

    void (async () => {
      const live = liveRef.current;
      if (live) {
        pushLog("LIVE :: Connecting Gemini Live…");
        setMode("listening");
        const ok = await live.start({ uiLanguage: "English", voice: "female" });
        if (ok) {
          const micOk = await live.startMic();
          if (micOk) {
            liveActiveRef.current = true;
            setLiveActive(true);
            pushLog("AUDIO :: Live mic streaming");
            return;
          }
          live.stop();
        }
        pushLog("LIVE :: Falling back to Web Speech + HTTP turn");
      }

      const Ctor = getSpeechCtor();
      if (!Ctor) {
        setError("Speech recognition is not supported in this browser. Use text chat.");
        setMode("idle");
        return;
      }

      finalChunks.current = [];
      interimRef.current = "";
      setInterim("");
      setMode("listening");
      pushLog("AUDIO :: Listening for operator…");

      const rec = new Ctor();
      rec.lang = "en-US";
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;

      rec.onresult = (event) => {
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const text = result[0]?.transcript ?? "";
          if (result.isFinal) {
            finalChunks.current.push(text.trim());
          } else {
            interimText += text;
          }
        }
        interimRef.current = interimText.trim();
        setInterim(interimRef.current);
        if (interimText || finalChunks.current.length) {
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
        if (event.error === "no-speech" || event.error === "aborted") return;
        if (event.error === "not-allowed") {
          setError("Microphone permission denied. You can still type.");
        } else {
          setError(`Speech error: ${event.error}`);
        }
      };

      rec.onend = () => {
        clearSilence();
        recRef.current = null;
        const spoken = [...finalChunks.current, interimRef.current]
          .filter(Boolean)
          .join(" ")
          .trim();
        finalChunks.current = [];
        interimRef.current = "";
        setInterim("");
        if (spoken) {
          void runTurn(spoken);
        } else if (!busyRef.current) {
          setMode("idle");
          pushLog("IDLE :: No speech captured");
        }
      };

      recRef.current = rec;
      try {
        rec.start();
      } catch {
        setError("Could not start the microphone.");
        setMode("idle");
      }
    })();
  }, [boot.status, pushLog, runTurn, stopPlayback]);

  const toggleListening = useCallback(() => {
    if (mode === "listening" || liveActive) {
      liveRef.current?.stopMic();
      liveRef.current?.stop();
      liveActiveRef.current = false;
      setLiveActive(false);
      stopMic();
      setMode("idle");
      return;
    }
    if (mode === "idle" || mode === "speaking") {
      startListening();
    }
  }, [mode, liveActive, startListening, stopMic]);

  const submitText = useCallback(
    (text: string) => {
      if (mode === "listening") stopMic();
      void runTurn(text);
    },
    [mode, runTurn, stopMic],
  );

  const newRequest = useCallback(async () => {
    stopMic();
    stopPlayback();
    liveRef.current?.stop();
    liveActiveRef.current = false;
    setLiveActive(false);
    matchRef.current = null;
    intentRef.current = null;
    setMatch(null);
    setInterim("");
    setError(null);
    setMode("idle");
    pushLog("SES :: New request — clearing voice session");
    try {
      await api.clearVoiceSession();
    } catch {
      /* best-effort */
    }
    setMessages([
      {
        id: uid(),
        role: "assistant",
        text: "Ready for a fresh request. How can I help?",
      },
    ]);
  }, [pushLog, stopMic, stopPlayback]);

  useEffect(
    () => () => {
      clearSilence();
      try {
        recRef.current?.abort();
      } catch {
        /* ignore */
      }
      stopPlayback();
    },
    [stopPlayback],
  );

  const connectionStatus: SessionStatus =
    boot.status === "online"
      ? "online"
      : boot.status === "booting"
        ? "booting"
        : "degraded";

  return {
    mode,
    messages,
    interim,
    match,
    logs,
    error,
    micSupported,
    lastLatencyMs,
    connectionStatus,
    bootMessage: boot.message,
    busy: busyRef.current || mode === "thinking" || mode === "speaking",
    submitText,
    toggleListening,
    newRequest,
  };
}
