import { FormEvent, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import type { ConditionTerm, PatientProfile } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

const LANGUAGES = ['Sinhala', 'Tamil', 'English'] as const;
const CARE_LEVELS = ['basic', 'intermediate', 'advanced'] as const;
const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'unknown'] as const;

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

function splitList(value: string): string[] {
  return value
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function PatientOnboardingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [conditions, setConditions] = useState<ConditionTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('English');
  const [languages, setLanguages] = useState<string[]>(['English']);
  const [city, setCity] = useState('Colombo');
  const [longitude, setLongitude] = useState(79.8612);
  const [latitude, setLatitude] = useState(6.9271);

  const [heightCm, setHeightCm] = useState('');
  const [weightKg, setWeightKg] = useState('');
  const [bloodType, setBloodType] = useState('unknown');
  const [selectedConditions, setSelectedConditions] = useState<string[]>([]);
  const [medicationsText, setMedicationsText] = useState('');
  const [allergiesText, setAllergiesText] = useState('');

  const [careLevel, setCareLevel] = useState('basic');
  const [emergencyName, setEmergencyName] = useState('');
  const [emergencyPhone, setEmergencyPhone] = useState('');

  useEffect(() => {
    if (user?.role !== 'patient') return;
    let cancelled = false;
    setLoading(true);
    Promise.all([api.myPatientProfile(), api.vocabConditions()])
      .then(([p, vocab]) => {
        if (cancelled) return;
        setProfile(p);
        setDisplayName(p.display_name || '');
        setPreferredLanguage(p.preferred_language || 'English');
        setLanguages(p.languages?.length ? p.languages : ['English']);
        setCity(p.city || 'Colombo');
        if (p.longitude != null && p.latitude != null) {
          setLongitude(p.longitude);
          setLatitude(p.latitude);
        }
        setHeightCm(p.height_cm != null ? String(p.height_cm) : '');
        setWeightKg(p.weight_kg != null ? String(p.weight_kg) : '');
        setBloodType(p.blood_type || 'unknown');
        setSelectedConditions(p.conditions || []);
        setMedicationsText((p.medications || []).join(', '));
        setAllergiesText((p.allergies || []).join(', '));
        setCareLevel(p.care_level || 'basic');
        setEmergencyName(p.emergency_contact_name || '');
        setEmergencyPhone(p.emergency_contact_phone || '');
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
  const steps = ['About you', 'Health snapshot', 'Emergency & care level'];

  const stepPayload = useMemo(() => {
    if (step === 0) {
      return {
        display_name: displayName.trim(),
        preferred_language: preferredLanguage,
        languages,
        city,
        longitude,
        latitude,
      };
    }
    if (step === 1) {
      return {
        height_cm: heightCm ? Number(heightCm) : undefined,
        weight_kg: weightKg ? Number(weightKg) : undefined,
        blood_type: bloodType,
        conditions: selectedConditions,
        medications: splitList(medicationsText),
        allergies: splitList(allergiesText),
      };
    }
    return {
      care_level: careLevel,
      emergency_contact_name: emergencyName.trim(),
      emergency_contact_phone: emergencyPhone.trim(),
    };
  }, [
    step,
    displayName,
    preferredLanguage,
    languages,
    city,
    longitude,
    latitude,
    heightCm,
    weightKg,
    bloodType,
    selectedConditions,
    medicationsText,
    allergiesText,
    careLevel,
    emergencyName,
    emergencyPhone,
  ]);

  if (user?.role !== 'patient') {
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

  function toggleCondition(slug: string) {
    setSelectedConditions((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  }

  async function saveStep(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateMyPatientProfile(stepPayload);
      setProfile(updated);
      if (step < 2) {
        setStep(step + 1);
      } else {
        navigate('/', { replace: true });
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
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Patient onboarding</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-mist">{steps[step]}</h1>
        <OnboardingProgressBar completion={completion} />
        <p className="mt-2 text-sm text-muted">
          Profile {completion}% complete — need 80% to request care.
        </p>
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
                <Field label="Preferred language">
                  <select
                    value={preferredLanguage}
                    onChange={(e) => setPreferredLanguage(e.target.value)}
                    className={inputClass}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Languages spoken">
                  <motionLanguageRow languages={languages} toggleLanguage={toggleLanguage} />
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
                <motionHealthFields
                  heightCm={heightCm}
                  setHeightCm={setHeightCm}
                  weightKg={weightKg}
                  setWeightKg={setWeightKg}
                  bloodType={bloodType}
                  setBloodType={setBloodType}
                />
                <Field label="Known conditions (medical vocabulary)">
                  <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
                    {conditions.map((c) => (
                      <button
                        key={c.slug}
                        type="button"
                        onClick={() => toggleCondition(c.slug)}
                        className={`rounded-full border px-3 py-1 text-xs ${
                          selectedConditions.includes(c.slug)
                            ? 'border-mint text-mint'
                            : 'border-hair text-muted hover:border-cyan/40'
                        }`}
                      >
                        {c.canonical_en}
                      </button>
                    ))}
                  </div>
                </Field>
                <Field label="Medications (comma-separated)">
                  <textarea
                    value={medicationsText}
                    onChange={(e) => setMedicationsText(e.target.value)}
                    rows={2}
                    className={inputClass}
                    placeholder="e.g. metformin, aspirin"
                  />
                </Field>
                <Field label="Allergies (comma-separated)">
                  <textarea
                    value={allergiesText}
                    onChange={(e) => setAllergiesText(e.target.value)}
                    rows={2}
                    className={inputClass}
                    placeholder="e.g. peanuts, penicillin"
                  />
                </Field>
              </>
            )}

            {step === 2 && (
              <>
                <Field label="Care level needed">
                  <select
                    value={careLevel}
                    onChange={(e) => setCareLevel(e.target.value)}
                    className={inputClass}
                  >
                    {CARE_LEVELS.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Emergency contact name">
                  <input
                    required
                    value={emergencyName}
                    onChange={(e) => setEmergencyName(e.target.value)}
                    className={inputClass}
                  />
                </Field>
                <Field label="Emergency contact phone">
                  <input
                    required
                    value={emergencyPhone}
                    onChange={(e) => setEmergencyPhone(e.target.value)}
                    className={inputClass}
                    placeholder="+94…"
                  />
                </Field>
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

function motionLanguageRow({
  languages,
  toggleLanguage,
}: {
  languages: string[];
  toggleLanguage: (lang: string) => void;
}) {
  return (
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
  );
}

function motionHealthFields({
  heightCm,
  setHeightCm,
  weightKg,
  setWeightKg,
  bloodType,
  setBloodType,
}: {
  heightCm: string;
  setHeightCm: (v: string) => void;
  weightKg: string;
  setWeightKg: (v: string) => void;
  bloodType: string;
  setBloodType: (v: string) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Field label="Height (cm)">
        <input
          type="number"
          min={50}
          max={250}
          required
          value={heightCm}
          onChange={(e) => setHeightCm(e.target.value)}
          className={inputClass}
        />
      </Field>
      <Field label="Weight (kg)">
        <input
          type="number"
          min={20}
          max={300}
          step={0.1}
          required
          value={weightKg}
          onChange={(e) => setWeightKg(e.target.value)}
          className={inputClass}
        />
      </Field>
      <Field label="Blood type">
        <select
          value={bloodType}
          onChange={(e) => setBloodType(e.target.value)}
          className={inputClass}
        >
          {BLOOD_TYPES.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );
}
