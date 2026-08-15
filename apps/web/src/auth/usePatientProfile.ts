import { useCallback, useEffect, useState } from 'react';
import type { PatientProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

export function usePatientProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [loading, setLoading] = useState(user?.role === 'patient');

  const refresh = useCallback(async () => {
    if (user?.role !== 'patient') {
      setProfile(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setProfile(await api.myPatientProfile());
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [user?.role, user?.id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    profile,
    setProfile,
    loading,
    refresh,
    canRequestCare: user?.role !== 'patient' || profile?.can_request_care === true,
    completionPercent: profile?.completion_percent ?? 0,
  };
}
