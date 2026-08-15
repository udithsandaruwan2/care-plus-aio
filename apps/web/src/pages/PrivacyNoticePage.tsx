import { Link } from 'react-router-dom';
import { BackLink } from '../components/ui/BackLink';
import { PageHeader } from '../components/ui/PageHeader';
import { SUPPORT_EMAIL } from '../config';

export function PrivacyNoticePage() {
  return (
    <div className="mx-auto max-w-2xl">
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Privacy"
          title="Personal data notice (PDPA)"
          subtitle="How Care Plus handles personal and health-related data in Sri Lanka. This is an operational notice for the research platform, not legal advice."
        />
      </div>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted">
        <section>
          <h2 className="font-display text-lg text-mist">Who we are</h2>
          <p className="mt-2">
            Care Plus matches patients with caregivers using voice, profiles, and (with consent) AI
            processing. Controller contact:{' '}
            <a className="text-cyan hover:underline" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>
            . Hours: Monday–Saturday, 08:00–20:00 Asia/Colombo.
          </p>
        </section>

        <section>
          <h2 className="font-display text-lg text-mist">What we collect</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Account: email, name, role (patient or caregiver), authentication tokens.</li>
            <li>
              Care profiles: languages, location, specialties, availability, onboarding answers.
            </li>
            <li>Voice and chat: transcripts and structured intent when you use Serah.</li>
            <li>Health records and wearable metrics you or a linked caregiver submit.</li>
            <li>
              Hire flow: care requests, messages, payments (Stripe demo gateway or PayHere),
              reviews.
            </li>
            <li>Device: optional push tokens; browser language preference.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-display text-lg text-mist">Consent and AI</h2>
          <p className="mt-2">
            Voice → intent and match pipelines that call external AI (for example Gemini) run only
            after you grant <strong className="text-mist">AI processing</strong> consent. Ranking of
            caregivers is done by the on-platform VEHMF engine, not by a generative model.
          </p>
        </section>

        <section>
          <h2 className="font-display text-lg text-mist">Your rights</h2>
          <p className="mt-2">
            Signed-in users can download a copy of their data (JSON or PDF) and request erasure from{' '}
            <Link className="text-cyan hover:underline" to="/settings/privacy">
              Account → Privacy
            </Link>
            . Erasure removes or anonymises account data and related health/voice records, subject
            to legal retention of audit logs.
          </p>
        </section>

        <section>
          <h2 className="font-display text-lg text-mist">Security</h2>
          <p className="mt-2">
            Production traffic is HTTPS (TLS 1.3 at the reverse proxy). Sensitive fields are
            encrypted at rest. Access to another person’s health data is role-gated and audited.
          </p>
        </section>
      </div>
    </div>
  );
}
