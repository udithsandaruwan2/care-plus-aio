import { useEffect } from 'react';
import { AssistantState } from '@care-plus/core';
import { useAuth } from '../auth/AuthContext';
import { useConnectionStore } from '../auth/connectionStore';
import { loadLastMatch } from '../lib/query/matchCache';
import { useAssistant } from './store';

/** Restore the last match from IndexedDB when the Serah store is empty (Step 94). */
export function useHydrateLastMatch() {
  const { user } = useAuth();
  const online = useConnectionStore((s) => s.browserOnline);
  const match = useAssistant((s) => s.match);
  const setMatch = useAssistant((s) => s.setMatch);
  const setState = useAssistant((s) => s.setState);

  useEffect(() => {
    if (!user?.id || match) return;
    let cancelled = false;
    void loadLastMatch(user.id).then((row) => {
      if (cancelled || !row || useAssistant.getState().match) return;
      setMatch(row.match, {
        fromCache: true,
        stale: row.stale || !online,
      });
      setState(AssistantState.RESULTS, { force: true });
    });
    return () => {
      cancelled = true;
    };
  }, [user?.id, match, online, setMatch, setState]);
}
