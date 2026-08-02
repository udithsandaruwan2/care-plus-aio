import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function PrivacySettingsPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<'json' | 'pdf' | 'erase' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  async function onExport(format: 'json' | 'pdf') {
    setBusy(format);
    setError(null);
    setMessage(null);
    try {
      if (format === 'pdf') {
        const blob = (await api.exportPrivacyData('pdf')) as Blob;
        downloadBlob(blob, 'careplus-data-export.pdf');
      } else {
        const data = (await api.exportPrivacyData('json')) as Record<string, unknown>;
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        downloadBlob(blob, 'careplus-data-export.json');
      }
      setMessage(`Downloaded ${format.toUpperCase()} export.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setBusy(null);
    }
  }

  async function onErase() {
    setBusy('erase');
    setError(null);
    setMessage(null);
    try {
      await api.eraseAccount(password, confirm || 'erase');
      setMessage('Account erased. Signing out…');
      logout();
      navigate('/login', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          err.body && typeof err.body === 'object' && 'detail' in err.body
            ? String((err.body as { detail: unknown }).detail)
            : err.message;
        setError(detail);
      } else {
        setError(err instanceof Error ? err.message : 'Erase failed.');
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <PageHeader
        eyebrow="Privacy"
        title="Data export & erasure"
        subtitle="Download a copy of your Care Plus data, or permanently erase your account (PDPA)."
      />

      <section className="rounded-2xl border border-hair bg-panel/50 p-5">
        <p className="font-display text-lg text-mist">Export my data</p>
        <p className="mt-1 text-sm text-muted">
          Includes profile, consent history, voice intents, health samples, medical records, and
          messages you sent.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            tone="ghost"
            className="min-h-9 px-3 py-1.5 text-xs"
            disabled={busy !== null}
            onClick={() => void onExport('json')}
          >
            {busy === 'json' ? 'Preparing…' : 'Download JSON'}
          </Button>
          <Button
            tone="ghost"
            className="min-h-9 px-3 py-1.5 text-xs"
            disabled={busy !== null}
            onClick={() => void onExport('pdf')}
          >
            {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-rose/30 bg-panel/50 p-5">
        <p className="font-display text-lg text-mist">Erase my account</p>
        <p className="mt-1 text-sm text-muted">
          Deactivates your login, anonymizes identity, wipes health/intent data, and removes you
          from caregiver matching. Audit logs are retained for compliance.
        </p>
        <label className="mt-4 block text-sm text-muted">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-xl border border-hair bg-void px-3 py-2 text-mist"
            autoComplete="current-password"
          />
        </label>
        <label className="mt-3 block text-sm text-muted">
          Type <span className="text-mist">erase</span> to confirm
          <input
            type="text"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="mt-1 w-full rounded-xl border border-hair bg-void px-3 py-2 text-mist"
            placeholder="erase"
          />
        </label>
        <div className="mt-4">
          <Button
            tone="danger"
            className="min-h-9 px-3 py-1.5 text-xs"
            disabled={busy !== null || !password || confirm.trim().toLowerCase() !== 'erase'}
            onClick={() => void onErase()}
          >
            {busy === 'erase' ? 'Erasing…' : 'Permanently erase account'}
          </Button>
        </div>
      </section>

      {error && <p className="text-sm text-rose">{error}</p>}
      {message && <p className="text-sm text-mint">{message}</p>}
    </div>
  );
}
