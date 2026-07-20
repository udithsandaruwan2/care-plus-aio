import { useCallback, useEffect, useState } from 'react';
import type { CareRelationship } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

/** Loads the active primary care link for patient or caregiver home dashboards. */
export function useCurrentCareRelationship() {
  const { user } = useAuth();
  const [relationship, setRelationship] = useState<CareRelationship | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (user?.role !== 'patient' && user?.role !== 'caregiver') {
      setRelationship(null);
      return Promise.resolve(null);
    }
    setLoading(true);
    setError(null);
    return api
      .currentCareRelationship()
      .then((rel) => {
        setRelationship(rel);
        return rel;
      })
      .catch((err) => {
        setRelationship(null);
        setError(err instanceof Error ? err.message : 'Could not load current care link.');
        return null;
      })
      .finally(() => setLoading(false));
  }, [user?.role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { relationship, loading, error, refresh, clear: () => setRelationship(null) };
}
