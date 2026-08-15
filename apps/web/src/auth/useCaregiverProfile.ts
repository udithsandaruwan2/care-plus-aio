import { useCallback, useEffect, useState } from 'react';
import type { CaregiverMeProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

export function useCaregiverProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CaregiverMeProfile | null>(null);
  const [loading, setLoading] = useState(user?.role === 'caregiver');

  const refresh = useCallback(async () => {
    if (user?.role !== 'caregiver') {
      setProfile(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setProfile(await api.myCaregiverProfile());
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
    isMatchEligible: user?.role !== 'caregiver' || profile?.is_match_eligible === true,
    onboardingComplete: profile?.onboarding_complete === true,
    completionPercent: profile?.completion_percent ?? 0,
  };
}
