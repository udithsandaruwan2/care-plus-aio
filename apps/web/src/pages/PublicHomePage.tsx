import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Activity, HeartPulse, Mic, ShieldCheck } from 'lucide-react';
import { AssistantState } from '@care-plus/core';
import { NeuralOrb } from '../assistant/NeuralOrb';
import { Button } from '../components/ui/Button';

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  const [rotation, setRotation] = useState({ x: 0, y: 0 });
  const cardRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={cardRef}
      className="perspective-1000"
      onMouseMove={(e) => {
        const rect = cardRef.current?.getBoundingClientRect();
        if (!rect) return;
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setRotation({
          x: ((y - rect.height / 2) / (rect.height / 2)) * -8,
          y: ((x - rect.width / 2) / (rect.width / 2)) * 8,
        });
      }}
      onMouseLeave={() => setRotation({ x: 0, y: 0 })}
    >
      <div
        className="rounded-2xl border border-hair bg-panel p-6 shadow-[var(--cp-shadow-soft)] transition-transform duration-200"
        style={{ transform: `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg)` }}
      >
        <div className="mb-4 text-cyan">{icon}</div>
        <h3 className="font-display text-lg font-semibold text-mist">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
      </div>
    </div>
  );
}

export function PublicHomePage() {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="relative overflow-hidden bg-panel">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div
          className="absolute -right-24 -top-24 h-[500px] w-[500px] rounded-full bg-cyan/15 blur-[80px]"
          style={{ transform: `translate(${mousePos.x * -50}px, ${mousePos.y * -50}px)` }}
        />
        <div
          className="absolute -bottom-40 -left-40 h-[600px] w-[600px] rounded-full bg-violet/10 blur-[80px]"
          style={{ transform: `translate(${mousePos.x * 50}px, ${mousePos.y * 50}px)` }}
        />
      </div>

      <section className="relative z-10 mx-auto flex min-h-[calc(100vh-80px)] max-w-6xl items-center justify-between gap-10 px-6 py-16">
        <div className="max-w-xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan">
            <Activity size={14} /> Serah Neural Core v2.0
          </div>
          <h1
            className="font-display text-4xl font-bold leading-tight text-mist sm:text-5xl"
            style={{ transform: `translate(${mousePos.x * 12}px, ${mousePos.y * 12}px)` }}
          >
            Match with Caregivers
            <br />
            using your{' '}
            <span className="bg-gradient-to-r from-cyan to-violet bg-clip-text text-transparent">
              Voice.
            </span>
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-muted">
            Speak naturally in English, Sinhala, or Tamil. Serah captures your need; VEHMF ranks
            caregivers on skills, history, distance, and trust.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/app">
              <Button className="gap-2 px-6">
                <Mic size={18} />
                Initiate Voice Match
              </Button>
            </Link>
            <Link to="/caregivers">
              <Button tone="ghost" className="px-6">
                Explore Directory
              </Button>
            </Link>
          </div>
        </div>
        <div className="relative hidden lg:block" aria-hidden>
          <NeuralOrb visual="idle" state={AssistantState.IDLE} amplitude={0.22} variant="hero" />
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-20">
        <h2 className="text-center font-display text-2xl font-bold text-mist">
          Next-Level Innovation
        </h2>
        <div className="mx-auto mt-2 h-1 w-16 rounded-full bg-cyan" />
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <FeatureCard
            icon={<Mic size={32} />}
            title="Voice-First Matching"
            description="Tell Serah what you need. She captures condition, care level, and language to find your match."
          />
          <FeatureCard
            icon={<ShieldCheck size={32} />}
            title="VEHMF Verification"
            description="Every caregiver is ranked on skills, history, distance, and trust — never by a generative model."
          />
          <FeatureCard
            icon={<HeartPulse size={32} />}
            title="Secure Operations"
            description="Clear LKR pricing, demo checkout, and OTP-gated medical record sharing."
          />
        </div>
      </section>
    </div>
  );
}
