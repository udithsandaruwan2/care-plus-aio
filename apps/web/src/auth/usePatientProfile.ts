import { useCallback } from 'react';
import type { PatientProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { queryKeys, STALE_MS } from '../lib/query/keys';
import { useCachedQuery } from '../lib/query/useCachedQuery';

export function usePatientProfile() {
  const { user } = useAuth();
  const enabled = user?.role === 'patient' && Boolean(user?.id);
  const key = enabled ? queryKeys.patientProfile(user!.id) : null;

  const { data, loading, refresh, setData, fromCache, stale } = useCachedQuery<PatientProfile>({
    key,
    staleTimeMs: STALE_MS.profile,
    enabled,
    fetcher: () => api.myPatientProfile(),
  });

  const setProfile = useCallback(
    (value: PatientProfile | null | ((prev: PatientProfile | null) => PatientProfile | null)) => {
      const next = typeof value === 'function' ? value(data) : value;
      void setData(next);
    },
    [data, setData],
  );

  return {
    profile: data,
    setProfile,
    loading,
    refresh: () => refresh({ force: true }),
    fromCache,
    stale,
    canRequestCare: user?.role !== 'patient' || data?.can_request_care === true,
    completionPercent: data?.completion_percent ?? 0,
  };
}
