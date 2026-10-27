import { useEffect } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { publicDocsUrl } from '../lib/publicDocs';

/** Full-page recovery when a CDN or old SW served the SPA for a research file URL. */
export function ResearchFileGate() {
  const { '*': rest } = useParams();
  const { search } = useLocation();

  useEffect(() => {
    const target = publicDocsUrl(rest || '') + search;
    window.location.replace(target);
  }, [rest, search]);

  return <p className="px-6 py-12 text-sm text-muted">Opening document…</p>;
}
