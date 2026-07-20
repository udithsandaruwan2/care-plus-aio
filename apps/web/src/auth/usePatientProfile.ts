import { useEffect, useState } from 'react';
import type { PatientProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

export function usePatientProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [loading, setLoading] = useState(user?.role === 'patient');

  useEffect(() => {
    if (user?.role !== 'patient') {
      setProfile(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .myPatientProfile()
      .then((p) => {
        if (!cancelled) setProfile(p);
      })
      .catch(() => {
        if (!cancelled) setProfile(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role, user?.id]);

  return {
    profile,
    loading,
    canRequestCare: user?.role !== 'patient' || profile?.can_request_care === true,
    completionPercent: profile?.completion_percent ?? 0,
  };
}
