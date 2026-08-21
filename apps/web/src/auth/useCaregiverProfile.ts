import { useCallback } from 'react';
import type { CaregiverMeProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { queryKeys, STALE_MS } from '../lib/query/keys';
import { useCachedQuery } from '../lib/query/useCachedQuery';

export function useCaregiverProfile() {
  const { user } = useAuth();
  const enabled = user?.role === 'caregiver' && Boolean(user?.id);
  const key = enabled ? queryKeys.caregiverMe(user!.id) : null;

  const { data, loading, refresh, setData, fromCache, stale } = useCachedQuery<CaregiverMeProfile>({
    key,
    staleTimeMs: STALE_MS.profile,
    enabled,
    fetcher: () => api.myCaregiverProfile(),
  });

  const setProfile = useCallback(
    (
      value:
        | CaregiverMeProfile
        | null
        | ((prev: CaregiverMeProfile | null) => CaregiverMeProfile | null),
    ) => {
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
    isMatchEligible: user?.role !== 'caregiver' || data?.is_match_eligible === true,
    onboardingComplete: data?.onboarding_complete === true,
    completionPercent: data?.completion_percent ?? 0,
  };
}
