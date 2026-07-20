import { useEffect, useState } from 'react';
import type { CaregiverMeProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

export function useCaregiverProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CaregiverMeProfile | null>(null);
  const [loading, setLoading] = useState(user?.role === 'caregiver');

  useEffect(() => {
    if (user?.role !== 'caregiver') {
      setProfile(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .myCaregiverProfile()
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
    isMatchEligible: user?.role !== 'caregiver' || profile?.is_match_eligible === true,
    onboardingComplete: profile?.onboarding_complete === true,
    completionPercent: profile?.completion_percent ?? 0,
  };
}
