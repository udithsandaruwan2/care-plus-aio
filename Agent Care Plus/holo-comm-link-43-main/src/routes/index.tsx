import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AudioWaveform,
  Bot,
  Cpu,
  Mic,
  MicOff,
  Radio,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { useMemo } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { MatchRail } from "@/components/MatchRail";
import { Button } from "@/components/ui/button";
import {
  useSerahPresent,
  type SerahMode,
} from "@/hooks/useSerahPresent";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Serah — Care Plus Agent" },
      {
        name: "description",
        content:
          "Serah voice interface for Care Plus caregiver matching — presentation demo.",
      },
      { property: "og:title", content: "Serah — Care Plus Agent" },
      {
        property: "og:description",
        content:
          "Serah voice interface for Care Plus caregiver matching — presentation demo.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SerahInterface,
});

function modeLabel(mode: SerahMode): string {
  switch (mode) {
    case "listening":
      return "Listening / signal acquired";
    case "thinking":
      return "Serah is thinking…";
    case "speaking":
      return "Synthesizing response";
    default:
      return "Awaiting directive";
  }
}

function Orb({ mode }: { mode: SerahMode }) {
  const speaking = mode === "speaking";
  const listening = mode === "listening";
  const thinking = mode === "thinking";
  const active = speaking || listening || thinking;
  const bars = useMemo(() => Array.from({ length: 26 }, (_, i) => i), []);

  return (
    <motion.div
      layout
      className="relative flex min-h-60 items-center justify-center sm:min-h-72"
    >
      <motion.div
        className="absolute size-64 rounded-full border border-cyan/15 sm:size-72"
        animate={{ rotate: 360 }}
        transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
      >
        {[0, 1, 2].map((n) => (
          <span
            key={n}
            className="absolute size-2 rounded-full bg-cyan shadow-[0_0_18px_var(--cyan)]"
            style={{
              top: `${12 + n * 31}%`,
              left: n === 1 ? "98%" : `${8 + n * 34}%`,
            }}
          />
        ))}
      </motion.div>
      <motion.div
        className="absolute size-52 rounded-full border border-dashed border-violet/35 sm:size-60"
        animate={{ rotate: -360 }}
        transition={{ duration: 17, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="relative flex size-36 items-center justify-center rounded-full border border-cyan/60 bg-card sm:size-44"
        animate={{
          scale: speaking
            ? [1, 1.12, 0.96, 1.08, 1]
            : listening
              ? [1, 1.08, 1]
              : thinking
                ? [1, 1.04, 1]
                : [1, 1.025, 1],
          boxShadow: speaking
            ? [
                "0 0 40px var(--cyan-dim), inset 0 0 28px var(--violet)",
                "0 0 90px var(--violet), inset 0 0 42px var(--cyan)",
                "0 0 52px var(--cyan), inset 0 0 35px var(--violet)",
              ]
            : listening
              ? [
                  "0 0 38px var(--cyan-dim)",
                  "0 0 76px var(--cyan)",
                  "0 0 38px var(--cyan-dim)",
                ]
              : thinking
                ? [
                    "0 0 30px var(--violet)",
                    "0 0 55px var(--cyan-dim)",
                    "0 0 30px var(--violet)",
                  ]
                : [
                    "0 0 24px var(--cyan-dim)",
                    "0 0 45px var(--cyan-dim)",
                    "0 0 24px var(--cyan-dim)",
                  ],
        }}
        transition={{
          duration: speaking ? 0.75 : listening ? 1.3 : thinking ? 1.1 : 3.4,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        <motion.div
          className="absolute inset-3 rounded-full border border-cyan/35 bg-gradient-to-br from-cyan/15 via-transparent to-violet/25"
          animate={{ rotate: speaking || thinking ? 360 : -360 }}
          transition={{
            duration: speaking ? 2 : thinking ? 4 : 12,
            repeat: Infinity,
            ease: "linear",
          }}
        />
        <div className="flex h-20 items-center gap-1">
          {bars.map((bar) => (
            <motion.span
              key={bar}
              className="w-0.5 rounded-full bg-cyan shadow-[0_0_8px_var(--cyan)]"
              animate={{
                height: speaking
                  ? [8, 14 + ((bar * 13) % 42), 7]
                  : listening
                    ? [5, 9 + ((bar * 7) % 22), 5]
                    : thinking
                      ? [4, 8 + ((bar * 5) % 16), 4]
                      : [4, 7, 4],
              }}
              transition={{
                duration: speaking
                  ? 0.42 + (bar % 5) * 0.06
                  : active
                    ? 1.2
                    : 1.8,
                repeat: Infinity,
                delay: bar * 0.025,
              }}
            />
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

function NodeGraph({ mode }: { mode: SerahMode }) {
  const active = mode !== "idle";
  return (
    <div className="relative h-40 overflow-hidden border-y border-border bg-background/35">
      <svg
        viewBox="0 0 360 160"
        className="size-full"
        aria-label="Live neural pathway graph"
      >
        <g stroke="var(--cyan-dim)" strokeWidth="1" opacity="0.65">
          <line x1="38" y1="82" x2="108" y2="38" />
          <line x1="38" y1="82" x2="112" y2="126" />
          <line x1="108" y1="38" x2="190" y2="72" />
          <line x1="112" y1="126" x2="190" y2="72" />
          <line x1="190" y1="72" x2="264" y2="38" />
          <line x1="190" y1="72" x2="275" y2="120" />
          <line x1="264" y1="38" x2="328" y2="82" />
          <line x1="275" y1="120" x2="328" y2="82" />
        </g>
        {[
          [38, 82],
          [108, 38],
          [112, 126],
          [190, 72],
          [264, 38],
          [275, 120],
          [328, 82],
        ].map(([x, y], i) => (
          <motion.circle
            key={i}
            cx={x}
            cy={y}
            r="4"
            fill={i % 3 === 0 ? "var(--violet)" : "var(--cyan)"}
            animate={{
              r: active ? [3, 8, 3] : [3, 5, 3],
              opacity: [0.55, 1, 0.55],
            }}
            transition={{
              duration: mode === "speaking" ? 0.65 : 1.8,
              repeat: Infinity,
              delay: i * 0.16,
            }}
          />
        ))}
      </svg>
      <span className="absolute left-3 top-3 font-mono text-[9px] uppercase text-cyan/70">
        Neural route map / live
      </span>
    </div>
  );
}

function connectionLabel(status: string): { text: string; className: string } {
  if (status === "online")
    return { text: "Online", className: "text-terminal" };
  if (status === "booting")
    return { text: "Linking…", className: "text-cyan" };
  return { text: "Degraded", className: "text-amber-400" };
}

function SerahInterface() {
  const {
    mode,
    messages,
    interim,
    match,
    logs,
    error,
    micSupported,
    lastLatencyMs,
    connectionStatus,
    bootMessage,
    submitText,
    toggleListening,
    newRequest,
  } = useSerahPresent();

  const link = connectionLabel(connectionStatus);
  const orbMode: SerahMode = mode;
  const spectrumActive = mode !== "idle";

  return (
    <main className="cyber-grid relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="scanline pointer-events-none absolute inset-0 opacity-30" />
      <div className="relative z-10 grid min-h-screen grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(330px,30%)]">
        <motion.section
          layout
          className="flex min-h-screen min-w-0 flex-col border-b border-border lg:border-b-0 lg:border-r"
        >
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background/65 px-5 backdrop-blur-xl sm:px-8">
            <div className="flex items-center gap-3">
              <motion.div
                animate={{ rotate: mode === "speaking" ? 360 : 0 }}
                transition={{
                  duration: 2,
                  repeat: mode === "speaking" ? Infinity : 0,
                  ease: "linear",
                }}
                className="flex size-9 items-center justify-center border border-cyan/50 bg-cyan/10 text-cyan"
              >
                <Bot className="size-5" />
              </motion.div>
              <div>
                <h1 className="text-glow text-lg font-bold tracking-[0.18em] text-cyan">
                  SERAH
                </h1>
                <p className="font-mono text-[9px] uppercase text-muted-foreground">
                  Care Plus · voice agent
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 font-mono text-[10px] uppercase text-muted-foreground">
              <span className="hidden max-w-[14rem] truncate sm:inline" title={bootMessage}>
                {bootMessage}
              </span>
              <span
                className={`size-1.5 animate-pulse rounded-full ${
                  connectionStatus === "online"
                    ? "bg-terminal shadow-[0_0_10px_var(--terminal)]"
                    : "bg-amber-400"
                }`}
              />
              <span className={link.className}>{link.text}</span>
            </div>
          </header>

          <div className="flex flex-1 flex-col px-4 py-4 sm:px-8">
            <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col">
              <motion.div layout className="flex flex-col items-center">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
                  Primary cognition core
                </div>
                <Orb mode={orbMode} />
                <AnimatePresence mode="wait">
                  <motion.div
                    key={mode}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-cyan"
                  >
                    <Radio className="size-3" /> {modeLabel(mode)}
                  </motion.div>
                </AnimatePresence>
                {interim ? (
                  <p className="mb-3 max-w-xl text-center font-mono text-xs text-cyan/80">
                    “{interim}”
                  </p>
                ) : null}
                {error ? (
                  <p className="mb-3 max-w-xl text-center font-mono text-[10px] text-red-400">
                    {error}
                  </p>
                ) : null}
              </motion.div>

              {match?.results?.length ? (
                <MatchRail match={match} onClear={() => void newRequest()} />
              ) : null}

              <motion.div
                layout
                className="glass-panel mx-auto flex h-[min(36vh,310px)] w-full max-w-3xl flex-col overflow-hidden rounded-md"
              >
                <div className="flex h-9 shrink-0 items-center justify-between border-b border-border px-4 font-mono text-[9px] uppercase text-muted-foreground">
                  <span>Conversation stream</span>
                  <span>CH.01 / Encrypted</span>
                </div>
                <Conversation className="min-h-0">
                  <ConversationContent className="gap-4 p-4 sm:p-5">
                    {messages.map((message) => (
                      <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <Message from={message.role}>
                          <span className="font-mono text-[9px] uppercase text-cyan/70">
                            {message.role === "assistant" ? "SERAH" : "YOU"}
                          </span>
                          <MessageContent
                            className={
                              message.role === "user"
                                ? "border border-cyan/20 bg-cyan/10 font-mono text-primary-foreground"
                                : "font-mono text-xs leading-relaxed"
                            }
                          >
                            <MessageResponse
                              isAnimating={
                                message.role === "assistant" &&
                                mode === "speaking" &&
                                message.id === messages[messages.length - 1]?.id
                              }
                            >
                              {message.text}
                            </MessageResponse>
                          </MessageContent>
                        </Message>
                      </motion.div>
                    ))}
                  </ConversationContent>
                  <ConversationScrollButton />
                </Conversation>
                <div className="border-t border-border p-3">
                  <PromptInput
                    onSubmit={({ text }) => submitText(text)}
                    className="border-cyan/25 bg-background/60"
                  >
                    <PromptInputTextarea
                      placeholder="Say hi, or ask Serah to find a caregiver…"
                      className="min-h-12 font-mono text-xs"
                      disabled={
                        connectionStatus !== "online" ||
                        mode === "thinking" ||
                        mode === "speaking"
                      }
                    />
                    <PromptInputFooter className="justify-between">
                      <Button
                        type="button"
                        variant={mode === "listening" ? "default" : "ghost"}
                        size="icon-sm"
                        onClick={toggleListening}
                        disabled={
                          !micSupported ||
                          connectionStatus !== "online" ||
                          mode === "thinking"
                        }
                        aria-label={
                          mode === "listening"
                            ? "Stop listening"
                            : "Start listening"
                        }
                        title={
                          !micSupported
                            ? "Mic not supported — use text"
                            : mode === "listening"
                              ? "Stop listening"
                              : "Start listening"
                        }
                      >
                        {mode === "listening" ? <MicOff /> : <Mic />}
                      </Button>
                      <PromptInputSubmit
                        disabled={
                          connectionStatus !== "online" ||
                          mode === "thinking" ||
                          mode === "speaking"
                        }
                        status={
                          mode === "thinking" || mode === "speaking"
                            ? "streaming"
                            : "ready"
                        }
                      />
                    </PromptInputFooter>
                  </PromptInput>
                </div>
              </motion.div>
            </div>
          </div>
        </motion.section>

        <motion.aside
          layout
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          className="glass-panel flex min-h-[720px] flex-col rounded-none lg:min-h-screen"
        >
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-border px-5">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em]">
                <Activity className="size-4 text-cyan" /> Diagnostics & telemetry
              </h2>
              <p className="mt-1 font-mono text-[9px] text-muted-foreground">
                REALTIME PROCESS MONITOR
              </p>
            </div>
            <Cpu className="size-5 text-cyan/60" />
          </div>
          <div className="grid grid-cols-3 border-b border-border">
            {[
              {
                label: "LATENCY",
                value:
                  lastLatencyMs != null
                    ? `${String(lastLatencyMs).padStart(2, "0")}ms`
                    : "—",
              },
              {
                label: "LOAD",
                value:
                  mode === "speaking"
                    ? "82%"
                    : mode === "thinking"
                      ? "64%"
                      : mode === "listening"
                        ? "41%"
                        : "24%",
              },
              {
                label: "MODE",
                value: mode.slice(0, 4).toUpperCase(),
              },
            ].map((stat) => (
              <motion.div
                key={stat.label}
                layout
                className="border-r border-border px-3 py-4 last:border-r-0"
              >
                <p className="font-mono text-[8px] text-muted-foreground">
                  {stat.label}
                </p>
                <p className="mt-1 font-mono text-sm text-cyan">{stat.value}</p>
              </motion.div>
            ))}
          </div>
          <NodeGraph mode={orbMode} />
          <div className="border-b border-border p-4">
            <div className="mb-3 flex items-center justify-between font-mono text-[9px] uppercase text-muted-foreground">
              <span>Audio spectrum</span>
              <AudioWaveform className="size-4 text-violet" />
            </div>
            <div className="flex h-14 items-center justify-between gap-1">
              {Array.from({ length: 34 }, (_, i) => (
                <motion.span
                  key={i}
                  className="w-1 rounded-full bg-gradient-to-t from-violet to-cyan"
                  animate={{
                    height: spectrumActive
                      ? [6, 12 + ((i * 11) % 40), 7]
                      : [5, 10, 5],
                  }}
                  transition={{
                    duration: mode === "speaking" ? 0.38 : 1.4,
                    repeat: Infinity,
                    delay: i * 0.025,
                  }}
                />
              ))}
            </div>
          </div>
          <div className="flex min-h-0 flex-1 flex-col p-4">
            <div className="mb-3 flex items-center justify-between font-mono text-[9px] uppercase text-muted-foreground">
              <span>System event stream</span>
              <span className="text-terminal">● Recording</span>
            </div>
            <div className="min-h-48 flex-1 overflow-hidden border border-border bg-background/70 p-3 font-mono text-[9px] leading-6">
              <AnimatePresence initial={false}>
                {logs.map((log, index) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex gap-2"
                  >
                    <span className="text-muted-foreground">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span
                      className={
                        log.text.startsWith("ERR")
                          ? "text-red-400"
                          : log.text.startsWith("SEC") ||
                              log.text.startsWith("AUTH")
                            ? "text-terminal"
                            : "text-cyan"
                      }
                    >
                      {log.text}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
              <span className="mt-1 inline-block h-3 w-1.5 animate-pulse bg-cyan" />
            </div>
          </div>
          <div className="grid grid-cols-2 border-t border-border font-mono text-[9px] uppercase text-muted-foreground">
            <div className="flex items-center gap-2 border-r border-border p-4">
              <ShieldCheck className="size-4 text-terminal" />
              Protocol secure
            </div>
            <Button
              variant="ghost"
              className="h-auto justify-start rounded-none p-4 text-[9px] uppercase text-cyan"
              onClick={() => void newRequest()}
            >
              <Zap /> New request
            </Button>
          </div>
        </motion.aside>
      </div>
    </main>
  );
}
