/** SW-denylisted alias so research files are not captured as SPA navigations. */
export const PUBLIC_DOCS_BASE = '/api/public-docs';

export function publicDocsUrl(file = ''): string {
  const trimmed = file.replace(/^\/+/, '');
  return trimmed ? `${PUBLIC_DOCS_BASE}/${trimmed}` : PUBLIC_DOCS_BASE;
}

export function researchAssetRedirect(pathname: string, search = ''): string | null {
  if (pathname === '/docs' || pathname === '/docs/') {
    return PUBLIC_DOCS_BASE;
  }
  const match = pathname.match(/^\/research\/(.+)$/);
  if (match) {
    return `${PUBLIC_DOCS_BASE}/${match[1]}${search}`;
  }
  return null;
}
