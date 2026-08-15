import { useState } from 'react';
import type { CaregiverMeProfile, PatientProfile } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { mediaUrl } from '../lib/mediaUrl';

type Props = {
  role: 'patient' | 'caregiver';
  photoUrl?: string | null;
  documents?: Array<Record<string, unknown>>;
  onPatientPhoto?: (profile: PatientProfile) => void;
  onCaregiverProfile?: (profile: CaregiverMeProfile) => void;
};

export function ProfileMediaCard({
  role,
  photoUrl,
  documents,
  onPatientPhoto,
  onCaregiverProfile,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const src = mediaUrl(photoUrl);

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      if (role === 'patient') {
        onPatientPhoto?.(await api.uploadMyPatientPhoto(file, file.name));
      } else {
        onCaregiverProfile?.(await api.uploadMyCaregiverPhoto(file, file.name));
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Upload failed.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function onDocument(file: File | undefined) {
    if (!file || role !== 'caregiver') return;
    setBusy(true);
    setError(null);
    try {
      onCaregiverProfile?.(await api.uploadMyCaregiverDocument(file, file.name));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Upload failed.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-start gap-4">
      <div className="h-20 w-20 overflow-hidden rounded-2xl border border-hair bg-void/60">
        {src ? (
          <img src={src} alt="Profile" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted">
            No photo
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <label className="block text-sm text-mist">
          Profile photo
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={busy}
            className="mt-1 block w-full text-xs text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-cyan/20 file:px-3 file:py-1.5 file:text-cyan"
            onChange={(e) => void onPhoto(e.target.files?.[0])}
          />
        </label>
        {role === 'caregiver' && (
          <label className="block text-sm text-mist">
            Certification document
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/webp"
              disabled={busy}
              className="mt-1 block w-full text-xs text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-cyan/20 file:px-3 file:py-1.5 file:text-cyan"
              onChange={(e) => void onDocument(e.target.files?.[0])}
            />
          </label>
        )}
        {busy && <p className="text-xs text-muted">Uploading…</p>}
        {error && <p className="text-xs text-rose">{error}</p>}
        {role === 'caregiver' && documents && documents.length > 0 && (
          <ul className="space-y-1 text-xs text-muted">
            {documents.map((doc, i) => {
              const name = typeof doc.name === 'string' ? doc.name : `Document ${i + 1}`;
              const href =
                typeof doc.download_url === 'string' ? mediaUrl(doc.download_url) : undefined;
              return (
                <li key={typeof doc.id === 'string' ? doc.id : i}>
                  {href ? (
                    <a href={href} className="text-cyan hover:underline" target="_blank" rel="noreferrer">
                      {name}
                    </a>
                  ) : (
                    name
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
