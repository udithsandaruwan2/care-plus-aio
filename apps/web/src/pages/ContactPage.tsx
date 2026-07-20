import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { ApiError } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | null;
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.name) && body.name[0]) return String(body.name[0]);
    if (Array.isArray(body?.email) && body.email[0]) return String(body.email[0]);
    return `Request failed (${err.status}).`;
  }
  return err instanceof Error ? err.message : 'Something went wrong.';
}

/** Public marketing / appointment enquiry form (Step 27). */
export function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('English');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createLead({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        city: city.trim() || undefined,
        preferred_language: preferredLanguage || undefined,
        message: message.trim() || undefined,
        source: 'marketing_form',
      });
      setDone(true);
      setName('');
      setEmail('');
      setPhone('');
      setCity('');
      setMessage('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-lg flex-col px-6 py-16">
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">{brand.theme}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Contact Care Plus</h1>
        <p className="mt-2 text-sm text-muted">
          Tell us how we can help. Our team will follow up — no account required.
        </p>

        {done && (
          <p className="mt-6 rounded-xl border border-mint/40 bg-mint/5 px-4 py-3 text-sm text-mint">
            Thanks — we received your enquiry and will be in touch soon.
          </p>
        )}

        {error && (
          <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-4 rounded-2xl border border-hair bg-panel p-6 backdrop-blur-md"
        >
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Phone</span>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">City</span>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Language</span>
            <select
              value={preferredLanguage}
              onChange={(e) => setPreferredLanguage(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            >
              <option value="English">English</option>
              <option value="Sinhala">Sinhala</option>
              <option value="Tamil">Tamil</option>
            </select>
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Message</span>
            <textarea
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/40 px-3 py-2 text-sm text-mist outline-none focus:border-cyan"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-full bg-cyan/90 px-5 py-2.5 text-sm font-medium text-void transition hover:bg-cyan disabled:opacity-50"
          >
            {busy ? 'Sending…' : 'Send enquiry'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-cyan hover:underline">
            Sign in
          </Link>
        </p>
      </main>
    </AtmosphereShell>
  );
}
