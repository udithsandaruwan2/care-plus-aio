import { useEffect } from 'react';
import { AssistantState } from '@care-plus/core';
import { useAuth } from '../auth/AuthContext';
import { useConnectionStore } from '../auth/connectionStore';
import { loadLastMatch, persistLastMatch } from '../lib/query/matchCache';
import { useAssistant } from './store';
import { refreshHydratedMatch } from './useMatch';

/** Restore the last match from IndexedDB when the Serah store is empty (Step 94). */
export function useHydrateLastMatch() {
  const { user } = useAuth();
  const online = useConnectionStore((s) => s.browserOnline);
  const match = useAssistant((s) => s.match);
  const setMatch = useAssistant((s) => s.setMatch);
  const setIntent = useAssistant((s) => s.setIntent);
  const setState = useAssistant((s) => s.setState);

  useEffect(() => {
    if (!user?.id || match) return;
    let cancelled = false;
    void loadLastMatch(user.id).then((row) => {
      if (cancelled || !row || useAssistant.getState().match) return;

      // Online: never park a previous ranking behind "Cached · may be out of date".
      // Replay silently when we still have the intent; otherwise drop the record.
      if (online) {
        if (row.stale || !row.intent) {
          void persistLastMatch(user.id, null);
          return;
        }
        void refreshHydratedMatch(row.intent, row.match.request_id);
        return;
      }

      setMatch(row.match, { fromCache: true, stale: true });
      if (row.intent) setIntent(row.intent);
      setState(AssistantState.RESULTS, { force: true });
    });
    return () => {
      cancelled = true;
    };
  }, [user?.id, match, online, setMatch, setIntent, setState]);
}
