import { FileText, GitBranch, Layers, ShieldCheck } from 'lucide-react';
import { PublicPage } from '../components/layout/PublicPage';
import { BackLink } from '../components/ui/BackLink';
import { Card } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';

const PAPER = '/research/conference-paper.pdf?v=20261027';
const ARCHITECTURE = '/research/architecture.png';
const VEHMF = '/research/vehmf.png';
const GITHUB = 'https://github.com/udithsandaruwan2/care-plus-aio';

const downloads = [
  {
    href: PAPER,
    title: 'IEEE conference paper (PDF)',
    description:
      'Six-page research paper: voice-enabled hybrid caregiver matching for chronic care in Sri Lanka.',
    meta: 'PDF · 6 pages',
  },
  {
    href: ARCHITECTURE,
    title: 'Layered architecture',
    description:
      'Presentation, API, cognitive, decision, and data layers. The language model does not rank.',
    meta: 'PNG',
  },
  {
    href: VEHMF,
    title: 'VEHMF four-factor fusion',
    description: 'AHP weights 0.287 / 0.231 / 0.280 / 0.202 and the emergency medical-fit vector.',
    meta: 'PNG',
  },
  {
    href: '/privacy',
    title: 'PDPA privacy notice',
    description: 'Consent, retention, and how voice data is handled on the research platform.',
    meta: 'Web page',
  },
];

export function DocsPage() {
  return (
    <PublicPage className="max-w-3xl">
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Research"
          title="Care Plus documentation"
          subtitle="Public papers, architecture, and privacy notes for the NIBM research platform hosted at careplus.udithsandaruwan.com."
        />
      </div>

      <Card className="mt-8 space-y-4 text-sm leading-relaxed text-muted">
        <p>
          Care Plus is an AI-enhanced, voice-enabled personal healthcare assistant with integrated
          caregiver matching for chronic disease management in Sri Lanka. Spoken or typed requests
          in Sinhala, Tamil, or English become structured care intent. The Voice-Enhanced Hybrid
          Matching Framework (VEHMF) then ranks caregivers. A large language model supports dialogue
          only; it does not decide the order.
        </p>
        <p>
          This research was conducted at the School of Computing and Engineering, National Institute
          of Business Management (NIBM), and belongs to NIBM.
        </p>
      </Card>

      <h2 className="mt-10 font-display text-lg text-mist">Downloads and reports</h2>
      <ul className="mt-4 space-y-3">
        {downloads.map((item) => (
          <li key={item.href}>
            <a
              href={item.href}
              className="block rounded-2xl border border-hair bg-panel p-4 no-underline shadow-[var(--cp-shadow-soft)] transition hover:border-cyan"
              {...(/\.(?:pdf|png)(?:\?|$)/i.test(item.href)
                ? { target: '_blank', rel: 'noreferrer' }
                : {})}
            >
              <p className="font-display text-base text-mist">{item.title}</p>
              <p className="mt-1 text-sm text-muted">{item.description}</p>
              <p className="mt-2 text-xs uppercase tracking-wide text-cyan">{item.meta}</p>
            </a>
          </li>
        ))}
      </ul>

      <h2 className="mt-10 font-display text-lg text-mist">How the matcher works</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Card className="space-y-2 text-sm text-muted">
          <FileText className="text-cyan" size={20} aria-hidden />
          <p className="font-display text-mist">Voice to intent</p>
          <p>
            Serah fills condition, language, urgency, and place. Ranking is withheld until those
            slots are present. Consent is checked before audio leaves the device.
          </p>
        </Card>
        <Card className="space-y-2 text-sm text-muted">
          <Layers className="text-cyan" size={20} aria-hidden />
          <p className="font-display text-mist">Four-factor score</p>
          <p>
            Health, language and culture, travel, and trust are fused with stakeholder AHP weights
            from 379 consistent Colombo instrument matrices.
          </p>
        </Card>
        <Card className="space-y-2 text-sm text-muted">
          <ShieldCheck className="text-cyan" size={20} aria-hidden />
          <p className="font-display text-mist">Explainable by construction</p>
          <p>
            Factor bars on the shortlist are the same weighted terms that produce the rank, so the
            reason cannot drift from the order.
          </p>
        </Card>
        <Card className="space-y-2 text-sm text-muted">
          <GitBranch className="text-cyan" size={20} aria-hidden />
          <p className="font-display text-mist">Source</p>
          <p>
            Implementation and tests live in the public repository{' '}
            <a className="text-cyan hover:underline" href={GITHUB} target="_blank" rel="noreferrer">
              udithsandaruwan2/care-plus-aio
            </a>
            .
          </p>
        </Card>
      </div>
    </PublicPage>
  );
}
