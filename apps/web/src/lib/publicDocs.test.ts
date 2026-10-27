import { describe, expect, it } from 'vitest';
import { PUBLIC_DOCS_BASE, publicDocsUrl, researchAssetRedirect } from './publicDocs';

describe('researchAssetRedirect', () => {
  it('sends /docs to the SW-safe docs hub', () => {
    expect(researchAssetRedirect('/docs')).toBe(PUBLIC_DOCS_BASE);
  });

  it('sends research files to the SW-safe alias', () => {
    expect(researchAssetRedirect('/research/conference-paper.pdf')).toBe(
      `${PUBLIC_DOCS_BASE}/conference-paper.pdf`,
    );
    expect(researchAssetRedirect('/research/architecture.png', '?v=1')).toBe(
      `${PUBLIC_DOCS_BASE}/architecture.png?v=1`,
    );
  });

  it('leaves app routes alone', () => {
    expect(researchAssetRedirect('/')).toBeNull();
    expect(researchAssetRedirect('/login')).toBeNull();
  });
});

describe('publicDocsUrl', () => {
  it('joins file names under the public docs prefix', () => {
    expect(publicDocsUrl()).toBe(PUBLIC_DOCS_BASE);
    expect(publicDocsUrl('vehmf.png')).toBe(`${PUBLIC_DOCS_BASE}/vehmf.png`);
  });
});
