import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';
import { SUPPORT_EMAIL } from '../config';

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
    <div className="mx-auto max-w-xl">
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Contact"
          title="Talk to Care Plus Sri Lanka"
          subtitle={`Tell us about your care need. We follow up in English, Sinhala, or Tamil — or email ${SUPPORT_EMAIL}.`}
        />
      </div>

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

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Name</span>
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Email</span>
          <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Phone (+94)</span>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+94 7X XXX XXXX"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">City</span>
          <Input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="e.g. Colombo, Kandy, Galle"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Language</span>
          <select
            value={preferredLanguage}
            onChange={(e) => setPreferredLanguage(e.target.value)}
            className="min-h-11 w-full rounded-2xl border border-hair bg-elevated px-3.5 py-2.5 text-sm text-mist outline-none focus:border-strong"
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
            className="w-full rounded-2xl border border-hair bg-elevated px-3.5 py-2.5 text-sm text-mist outline-none focus:border-strong"
          />
        </label>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? 'Sending…' : 'Send enquiry'}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-muted">
        Already have an account?{' '}
        <Link to="/login" className="text-cyan hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
