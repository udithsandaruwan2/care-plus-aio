import { FormEvent, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import type { CaregiverMeProfile, ConditionTerm } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

const LANGUAGES = ['Sinhala', 'Tamil', 'English'] as const;
const CARE_LEVELS = ['basic', 'intermediate', 'advanced'] as const;
const CERTIFICATIONS = [
  'NVQ Level 4 Caregiving',
  'First Aid (Red Cross)',
  'CPR Certified',
  'Dementia Care Certificate',
  'Diabetes Educator (basic)',
  'Wound Care Basics',
  'Medication Administration',
  'Elder Care Specialist',
] as const;

const CITIES: { name: string; lon: number; lat: number }[] = [
  { name: 'Colombo', lon: 79.8612, lat: 6.9271 },
  { name: 'Kandy', lon: 80.6337, lat: 7.2906 },
  { name: 'Galle', lon: 80.221, lat: 6.0535 },
  { name: 'Jaffna', lon: 80.0255, lat: 9.6615 },
  { name: 'Negombo', lon: 79.8358, lat: 7.2083 },
  { name: 'Matara', lon: 80.555, lat: 5.9549 },
];

const inputClass =
  'w-full rounded-lg border border-hair bg-void/60 px-3 py-2 text-mist outline-none ring-cyan focus:ring-1';

export function CaregiverOnboardingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<CaregiverMeProfile | null>(null);
  const [conditions, setConditions] = useState<ConditionTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState('');
  const [nicId, setNicId] = useState('');
  const [city, setCity] = useState('Colombo');
  const [longitude, setLongitude] = useState(79.8612);
  const [latitude, setLatitude] = useState(6.9271);

  const [languages, setLanguages] = useState<string[]>(['English']);
  const [selectedSpecialties, setSelectedSpecialties] = useState<string[]>([]);
  const [careLevels, setCareLevels] = useState<string[]>(['basic']);
  const [certifications, setCertifications] = useState<string[]>([]);
  const [yearsExperience, setYearsExperience] = useState('');

  const [bio, setBio] = useState('');
  const [serviceRadiusKm, setServiceRadiusKm] = useState('25');
  const [certDocsNote, setCertDocsNote] = useState('');

  useEffect(() => {
    if (user?.role !== 'caregiver') return;
    let cancelled = false;
    setLoading(true);
    Promise.all([api.myCaregiverProfile(), api.vocabConditions()])
      .then(([p, vocab]) => {
        if (cancelled) return;
        setProfile(p);
        setDisplayName(p.display_name || '');
        setNicId(p.nic_id || '');
        setCity(p.city || 'Colombo');
        if (p.longitude != null && p.latitude != null) {
          setLongitude(p.longitude);
          setLatitude(p.latitude);
        }
        setLanguages(p.languages?.length ? p.languages : ['English']);
        setSelectedSpecialties(p.specialties || []);
        setCareLevels(p.care_levels?.length ? p.care_levels : ['basic']);
        setCertifications(p.certifications || []);
        setYearsExperience(p.years_experience != null ? String(p.years_experience) : '');
        setBio(p.bio || '');
        setServiceRadiusKm(String(p.service_radius_km ?? 25));
        const docs = p.certification_docs || [];
        if (docs.length) {
          setCertDocsNote(
            docs
              .map((d) => (typeof d.name === 'string' ? d.name : JSON.stringify(d)))
              .join(', '),
          );
        }
        setConditions(vocab.results);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load profile.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  const completion = profile?.completion_percent ?? 0;
  const steps = ['Identity & area', 'Skills & certifications', 'Bio & service radius'];

  const stepPayload = useMemo(() => {
    if (step === 0) {
      return {
        display_name: displayName.trim(),
        nic_id: nicId.trim(),
        city,
        longitude,
        latitude,
      };
    }
    if (step === 1) {
      return {
        languages,
        specialties: selectedSpecialties,
        care_levels: careLevels,
        certifications,
        years_experience: yearsExperience ? Number(yearsExperience) : undefined,
      };
    }
    const docNames = certDocsNote
      .split(/[,;\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    return {
      bio: bio.trim(),
      service_radius_km: serviceRadiusKm ? Number(serviceRadiusKm) : 25,
      certification_docs: docNames.map((name) => ({ name, status: 'pending' })),
    };
  }, [
    step,
    displayName,
    nicId,
    city,
    longitude,
    latitude,
    languages,
    selectedSpecialties,
    careLevels,
    certifications,
    yearsExperience,
    bio,
    serviceRadiusKm,
    certDocsNote,
  ]);

  if (user?.role !== 'caregiver') {
    return <Navigate to="/" replace />;
  }

  function onCityChange(name: string) {
    setCity(name);
    const hit = CITIES.find((c) => c.name === name);
    if (hit) {
      setLongitude(hit.lon);
      setLatitude(hit.lat);
    }
  }

  function toggleLanguage(lang: string) {
    setLanguages((prev) =>
      prev.includes(lang) ? prev.filter((l) => l !== lang) : [...prev, lang],
    );
  }

  function toggleSpecialty(slug: string) {
    setSelectedSpecialties((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  }

  function toggleCareLevel(level: string) {
    setCareLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level],
    );
  }

  function toggleCertification(cert: string) {
    setCertifications((prev) =>
      prev.includes(cert) ? prev.filter((c) => c !== cert) : [...prev, cert],
    );
  }

  async function saveStep(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateMyCaregiverProfile(stepPayload);
      setProfile(updated);
      if (step < 2) {
        setStep(step + 1);
      } else {
        navigate('/presence', { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save profile.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-2xl flex-col px-6 py-10">
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">
          Caregiver onboarding
        </p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-mist">{steps[step]}</h1>
        <OnboardingProgressBar completion={completion} />
        <p className="mt-2 text-sm text-muted">
          Profile {completion}% complete — need 80% to appear in patient match results.
        </p>
        <motionStepChips steps={steps} step={step} />

        {loading ? (
          <p className="mt-8 text-muted">Loading your profile…</p>
        ) : (
          <form
            onSubmit={(e) => void saveStep(e)}
            className="mt-8 space-y-5 rounded-2xl border border-hair bg-panel p-6 backdrop-blur-md"
          >
            {step === 0 && (
              <>
                <Field label="Display name">
                  <input
                    required
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="NIC / ID (placeholder)">
                  <input
                    required
                    value={nicId}
                    onChange={(e) => setNicId(e.target.value)}
                    className={inputClass}
                    placeholder="e.g. 199012345678"
                  />
                </Field>
                <Field label="City">
                  <select
                    value={city}
                    onChange={(e) => onCityChange(e.target.value)}
                    className={inputClass}
                  >
                    {CITIES.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            )}

            {step === 1 && (
              <>
                <Field label="Languages spoken">
                  <div className="flex flex-wrap gap-2">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => toggleLanguage(lang)}
                        className={`rounded-lg border px-3 py-1.5 text-sm ${
                          languages.includes(lang)
                            ? 'border-cyan text-cyan'
                            : 'border-hair text-muted hover:border-cyan/40'
                        }`}
                      >
                        {lang}
                      </button>
                    ))}
                  </div>
                </Field>
                <Field label="Specialties (medical vocabulary)">
                  <motionSpecialtyGrid
                    conditions={conditions}
                    selected={selectedSpecialties}
                    toggle={toggleSpecialty}
                  />
                </Field>
                <Field label="Care levels you support">
                  <motionCareLevelRow levels={careLevels} toggle={toggleCareLevel} />
                </Field>
                <Field label="Certifications">
                  <motionCertGrid certs={certifications} toggle={toggleCertification} />
                </Field>
                <Field label="Years of experience">
                  <input
                    type="number"
                    min={0}
                    max={60}
                    required
                    value={yearsExperience}
                    onChange={(e) => setYearsExperience(e.target.value)}
                    className={inputClass}
                  />
                </Field>
              </>
            )}

            {step === 2 && (
              <>
                <Field label="Short bio">
                  <textarea
                    required
                    rows={4}
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className={inputClass}
                    placeholder="Tell patients about your experience and approach…"
                  />
                </Field>
                <Field label="Service radius (km)">
                  <input
                    type="number"
                    min={1}
                    max={200}
                    required
                    value={serviceRadiusKm}
                    onChange={(e) => setServiceRadiusKm(e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Certification documents (names only — uploads in Step 22d)">
                  <textarea
                    rows={2}
                    value={certDocsNote}
                    onChange={(e) => setCertDocsNote(e.target.value)}
                    className={inputClass}
                    placeholder="e.g. First Aid certificate, NVQ Level 4"
                  />
                </Field>
                {profile?.is_match_eligible && (
                  <p className="text-sm text-mint">
                    Your profile is approved and eligible for matching.
                  </p>
                )}
                {profile?.onboarding_complete && !profile?.is_match_eligible && (
                  <p className="text-sm text-amber">
                    Onboarding complete — waiting for admin approval before you appear in match.
                  </p>
                )}
              </>
            )}

            {error && <p className="text-sm text-rose">{error}</p>}

            <div className="flex gap-3 pt-2">
              {step > 0 && (
                <button
                  type="button"
                  onClick={() => setStep(step - 1)}
                  className="rounded-lg border border-hair px-4 py-2 text-sm text-muted hover:border-cyan"
                >
                  Back
                </button>
              )}
              <button
                type="submit"
                disabled={saving}
                className="flex-1 rounded-lg bg-cyan/90 px-4 py-2.5 font-medium text-void hover:bg-cyan disabled:opacity-60"
              >
                {saving ? 'Saving…' : step < 2 ? 'Save & continue' : 'Finish onboarding'}
              </button>
            </div>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-muted">
          <Link to="/" className="text-cyan hover:underline">
            Back to Neural Core
          </Link>
        </p>
      </main>
    </AtmosphereShell>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
      {children}
    </label>
  );
}

function OnboardingProgressBar({ completion }: { completion: number }) {
  return (
    <div className="mt-4 h-2 overflow-hidden rounded-full bg-void/80">
      <div
        className="h-full rounded-full bg-gradient-to-r from-cyan to-mint transition-all"
        style={{ width: `${Math.min(100, completion)}%` }}
      />
    </div>
  );
}

function motionStepChips({ steps, step }: { steps: string[]; step: number }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {steps.map((label, i) => (
        <span
          key={label}
          className={`rounded-full px-2 py-0.5 text-xs ${
            i === step ? 'bg-cyan/20 text-cyan' : 'bg-void/60 text-muted'
          }`}
        >
          {i + 1}. {label}
        </span>
      ))}
    </div>
  );
}

function motionSpecialtyGrid({
  conditions,
  selected,
  toggle,
}: {
  conditions: ConditionTerm[];
  selected: string[];
  toggle: (slug: string) => void;
}) {
  return (
    <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
      {conditions.map((c) => (
        <button
          key={c.slug}
          type="button"
          onClick={() => toggle(c.slug)}
          className={`rounded-full border px-3 py-1 text-xs ${
            selected.includes(c.slug)
              ? 'border-mint text-mint'
              : 'border-hair text-muted hover:border-cyan/40'
          }`}
        >
          {c.canonical_en}
        </button>
      ))}
    </div>
  );
}

function motionCareLevelRow({
  levels,
  toggle,
}: {
  levels: string[];
  toggle: (level: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {CARE_LEVELS.map((level) => (
        <button
          key={level}
          type="button"
          onClick={() => toggle(level)}
          className={`rounded-lg border px-3 py-1.5 text-sm capitalize ${
            levels.includes(level)
              ? 'border-cyan text-cyan'
              : 'border-hair text-muted hover:border-cyan/40'
          }`}
        >
          {level}
        </button>
      ))}
    </div>
  );
}

function motionCertGrid({
  certs,
  toggle,
}: {
  certs: string[];
  toggle: (cert: string) => void;
}) {
  return (
    <div className="flex max-h-36 flex-wrap gap-2 overflow-y-auto">
      {CERTIFICATIONS.map((cert) => (
        <button
          key={cert}
          type="button"
          onClick={() => toggle(cert)}
          className={`rounded-full border px-3 py-1 text-xs ${
            certs.includes(cert)
              ? 'border-mint text-mint'
              : 'border-hair text-muted hover:border-cyan/40'
          }`}
        >
          {cert}
        </button>
      ))}
    </div>
  );
}
