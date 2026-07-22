import { FormEvent, useCallback, useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import type {
  ConditionTerm,
  MedicalRecordDetail,
  MedicalRecordList,
} from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { useCurrentCareRelationship } from '../auth/useCurrentCareRelationship';

const inputClass =
  'w-full rounded-lg border border-hair bg-void/60 px-3 py-2 text-mist outline-none ring-cyan focus:ring-1';

function apiOrigin(): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
  return base.replace(/\/api\/v1\/?$/, '');
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type RecordFormState = {
  condition_slug: string;
  title: string;
  description: string;
  sensitive_notes: string;
  recorded_at: string;
};

const emptyForm = (): RecordFormState => ({
  condition_slug: '',
  title: '',
  description: '',
  sensitive_notes: '',
  recorded_at: '',
});

export function MedicalRecordsPage() {
  const { user, logout } = useAuth();
  const care = useCurrentCareRelationship();
  const isPatient = user?.role === 'patient';
  const isCaregiver = user?.role === 'caregiver';

  const [rows, setRows] = useState<MedicalRecordList[]>([]);
  const [conditions, setConditions] = useState<ConditionTerm[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MedicalRecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<RecordFormState>(emptyForm);
  const [createFile, setCreateFile] = useState<File | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const loadList = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .listMedicalRecords()
      .then((data) => setRows(data))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load records.');
      })
      .finally(() => setLoading(false));
  }, []);

  const loadDetail = useCallback((id: number) => {
    setDetailLoading(true);
    setError(null);
    return api
      .getMedicalRecord(id)
      .then((data) => {
        setDetail(data);
        setForm({
          condition_slug: data.condition_slug,
          title: data.title,
          description: data.description ?? '',
          sensitive_notes: data.sensitive_notes ?? '',
          recorded_at: data.recorded_at?.slice(0, 10) ?? '',
        });
      })
      .catch((err) => {
        setDetail(null);
        setError(err instanceof Error ? err.message : 'Could not load record.');
      })
      .finally(() => setDetailLoading(false));
  }, []);

  useEffect(() => {
    if (!isPatient && !isCaregiver) {
      setLoading(false);
      return;
    }
    void loadList();
    if (isPatient) {
      api.vocabConditions().then((v) => setConditions(v.results)).catch(() => setConditions([]));
    }
  }, [isPatient, isCaregiver, loadList]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      setEditing(false);
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  if (user && user.role !== 'patient' && user.role !== 'caregiver') {
    return <Navigate to="/" replace />;
  }

  const partnerLabel =
    isCaregiver && care.relationship
      ? care.relationship.patient_display_name || care.relationship.patient_email
      : null;

  async function onSelectRecord(id: number) {
    setSelectedId(id);
    setShowCreate(false);
    setEditing(false);
  }

  async function onDownloadAttachment(attachmentId: number) {
    setBusy(true);
    try {
      const signed = await api.getMedicalRecordAttachmentDownloadUrl(attachmentId);
      window.open(`${apiOrigin()}${signed.url}`, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not get download link.');
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!form.condition_slug || !form.title.trim()) {
      setError('Condition and title are required.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createMedicalRecord({
        condition_slug: form.condition_slug,
        title: form.title.trim(),
        description: form.description,
        sensitive_notes: form.sensitive_notes,
        recorded_at: form.recorded_at || null,
        file: createFile ?? undefined,
      });
      setShowCreate(false);
      setCreateFile(null);
      setForm(emptyForm());
      await loadList();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create record.');
    } finally {
      setBusy(false);
    }
  }

  async function onSaveEdit(e: FormEvent) {
    e.preventDefault();
    if (selectedId == null) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateMedicalRecord(selectedId, {
        condition_slug: form.condition_slug,
        title: form.title.trim(),
        description: form.description,
        sensitive_notes: form.sensitive_notes,
        recorded_at: form.recorded_at || null,
      });
      setDetail(updated);
      setEditing(false);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update record.');
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (selectedId == null) return;
    if (!window.confirm('Remove this record from your vault? This cannot be undone.')) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteMedicalRecord(selectedId);
      setSelectedId(null);
      setDetail(null);
      setEditing(false);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete record.');
    } finally {
      setBusy(false);
    }
  }

  async function onUploadAttachment() {
    if (selectedId == null || !uploadFile) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadMedicalRecordAttachment(selectedId, uploadFile, uploadFile.name);
      setUploadFile(null);
      await loadDetail(selectedId);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload file.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-violet">
              {isCaregiver ? 'Patient health' : 'Records vault'}
            </p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">
              {isCaregiver ? 'Care records' : 'My medical records'}
            </h1>
            {isCaregiver && partnerLabel && (
              <p className="mt-2 text-sm text-muted">
                Viewing records for <span className="text-mist">{partnerLabel}</span> while your care
                link is active. Every view is audited.
              </p>
            )}
            {isCaregiver && !care.loading && !care.relationship && (
              <p className="mt-2 text-sm text-amber">
                No active care relationship — records appear only while you are linked to a patient.
              </p>
            )}
            {isPatient && (
              <p className="mt-2 text-sm text-muted">
                Store clinical notes and attachments. Linked caregivers can read while care is active.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Neural Core
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        {isCaregiver && (
          <p className="mt-4 rounded-xl border border-violet/30 bg-violet/5 px-4 py-3 text-xs text-violet">
            Read-only access · HIPAA/PDPA audit trail · active relationship required
          </p>
        )}

        {isPatient && !showCreate && (
          <button
            type="button"
            onClick={() => {
              setShowCreate(true);
              setSelectedId(null);
              setDetail(null);
              setForm(emptyForm());
              setCreateFile(null);
            }}
            className="mt-6 self-start rounded-lg border border-cyan/40 bg-cyan/10 px-4 py-2 text-sm text-cyan transition hover:bg-cyan/20"
          >
            + New record
          </button>
        )}

        {error && (
          <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {isPatient && showCreate && (
          <form
            onSubmit={(e) => void onCreate(e)}
            className="mt-6 space-y-4 rounded-2xl border border-cyan/30 bg-panel/70 p-5 backdrop-blur-md"
          >
            <h2 className="font-display text-lg text-mist">New record</h2>
            <label className="block text-sm text-muted">
              Condition
              <select
                className={`${inputClass} mt-1`}
                value={form.condition_slug}
                onChange={(e) => setForm((f) => ({ ...f, condition_slug: e.target.value }))}
                required
              >
                <option value="">Select condition…</option>
                {conditions.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.canonical_en}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm text-muted">
              Title
              <input
                className={`${inputClass} mt-1`}
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                required
              />
            </label>
            <label className="block text-sm text-muted">
              Description
              <textarea
                className={`${inputClass} mt-1 min-h-[80px]`}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </label>
            <label className="block text-sm text-muted">
              Sensitive notes (encrypted)
              <textarea
                className={`${inputClass} mt-1 min-h-[80px]`}
                value={form.sensitive_notes}
                onChange={(e) => setForm((f) => ({ ...f, sensitive_notes: e.target.value }))}
              />
            </label>
            <label className="block text-sm text-muted">
              Recorded date
              <input
                type="date"
                className={`${inputClass} mt-1`}
                value={form.recorded_at}
                onChange={(e) => setForm((f) => ({ ...f, recorded_at: e.target.value }))}
              />
            </label>
            <label className="block text-sm text-muted">
              Attachment (optional)
              <input
                type="file"
                className="mt-1 block w-full text-sm text-muted"
                onChange={(e) => setCreateFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-cyan px-4 py-2 text-sm font-medium text-void disabled:opacity-50"
              >
                {busy ? 'Saving…' : 'Create record'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-hair px-4 py-2 text-sm text-muted"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {loading && <p className="mt-8 text-sm text-muted">Loading records…</p>}

        {!loading && !showCreate && rows.length === 0 && (
          <p className="mt-8 text-sm text-muted">
            {isCaregiver
              ? 'No records for your active patient yet.'
              : 'No records yet — add your first clinical note above.'}
          </p>
        )}

        {!showCreate && rows.length > 0 && (
          <ul className="mt-6 space-y-3">
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => void onSelectRecord(row.id)}
                  className={`w-full rounded-2xl border p-5 text-left backdrop-blur-md transition ${
                    selectedId === row.id
                      ? 'border-cyan/50 bg-cyan/5'
                      : 'border-hair bg-panel/70 hover:border-cyan/30'
                  }`}
                >
                  <p className="font-display text-lg text-mist">{row.title}</p>
                  <p className="mt-1 text-xs text-muted">
                    {row.condition_name} · {formatDate(row.recorded_at)} · {row.attachment_count}{' '}
                    attachment{row.attachment_count === 1 ? '' : 's'}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}

        {selectedId != null && !showCreate && (
          <section className="mt-8 rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md">
            {detailLoading && <p className="text-sm text-muted">Loading detail…</p>}
            {!detailLoading && detail && (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">{detail.condition_name}</p>
                    <h2 className="mt-1 font-display text-xl text-mist">{detail.title}</h2>
                    <p className="mt-1 text-xs text-muted">
                      Recorded {formatDate(detail.recorded_at)} · updated{' '}
                      {formatDate(detail.updated_at)}
                    </p>
                  </div>
                  {isPatient && !editing && (
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setEditing(true)}
                        className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void onDelete()}
                        disabled={busy}
                        className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>

                {editing && isPatient ? (
                  <form onSubmit={(e) => void onSaveEdit(e)} className="mt-4 space-y-3">
                    <label className="block text-sm text-muted">
                      Condition
                      <select
                        className={`${inputClass} mt-1`}
                        value={form.condition_slug}
                        onChange={(e) => setForm((f) => ({ ...f, condition_slug: e.target.value }))}
                      >
                        {conditions.map((c) => (
                          <option key={c.slug} value={c.slug}>
                            {c.canonical_en}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-sm text-muted">
                      Title
                      <input
                        className={`${inputClass} mt-1`}
                        value={form.title}
                        onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                      />
                    </label>
                    <label className="block text-sm text-muted">
                      Description
                      <textarea
                        className={`${inputClass} mt-1 min-h-[80px]`}
                        value={form.description}
                        onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                      />
                    </label>
                    <label className="block text-sm text-muted">
                      Sensitive notes
                      <textarea
                        className={`${inputClass} mt-1 min-h-[80px]`}
                        value={form.sensitive_notes}
                        onChange={(e) => setForm((f) => ({ ...f, sensitive_notes: e.target.value }))}
                      />
                    </label>
                    <label className="block text-sm text-muted">
                      Recorded date
                      <input
                        type="date"
                        className={`${inputClass} mt-1`}
                        value={form.recorded_at}
                        onChange={(e) => setForm((f) => ({ ...f, recorded_at: e.target.value }))}
                      />
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={busy}
                        className="rounded-lg bg-cyan px-4 py-2 text-sm text-void disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(false)}
                        className="rounded-lg border border-hair px-4 py-2 text-sm text-muted"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    {detail.description && (
                      <p className="mt-4 text-sm text-mist/90 whitespace-pre-wrap">{detail.description}</p>
                    )}
                    {detail.sensitive_notes && (
                      <div className="mt-4 rounded-xl border border-violet/30 bg-violet/5 px-4 py-3">
                        <p className="text-xs uppercase tracking-wide text-violet">Sensitive notes</p>
                        <p className="mt-2 text-sm text-mist whitespace-pre-wrap">{detail.sensitive_notes}</p>
                      </div>
                    )}
                  </>
                )}

                <div className="mt-6">
                  <h3 className="font-display text-sm text-mist">Attachments</h3>
                  {(detail.attachments ?? []).length === 0 && (
                    <p className="mt-2 text-sm text-muted">No attachments.</p>
                  )}
                  <ul className="mt-2 space-y-2">
                    {(detail.attachments ?? []).map((att) => (
                      <li
                        key={att.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-hair px-3 py-2"
                      >
                        <span className="text-sm text-mist">
                          {att.original_name}{' '}
                          <span className="text-xs text-muted">({formatBytes(att.size_bytes)})</span>
                        </span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void onDownloadAttachment(att.id)}
                          className="rounded border border-cyan/40 px-2 py-1 text-xs text-cyan"
                        >
                          Download
                        </button>
                      </li>
                    ))}
                  </ul>
                  {isPatient && !editing && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <input
                        type="file"
                        className="text-sm text-muted"
                        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                      />
                      <button
                        type="button"
                        disabled={busy || !uploadFile}
                        onClick={() => void onUploadAttachment()}
                        className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan disabled:opacity-50"
                      >
                        Upload
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </AtmosphereShell>
  );
}
