import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { DocsPage } from './DocsPage';

describe('DocsPage', () => {
  it('lists the conference paper and architecture downloads', () => {
    render(
      <MemoryRouter>
        <DocsPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: /care plus documentation/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ieee conference paper/i })).toHaveAttribute(
      'href',
      '/api/public-docs/conference-paper.pdf',
    );
    expect(screen.getByRole('link', { name: /layered architecture/i })).toHaveAttribute(
      'href',
      '/api/public-docs/architecture.png',
    );
  });
});

describe('public research files', () => {
  it('ships the conference paper and diagrams in public/research', () => {
    const root = resolve(__dirname, '../../public/research');
    expect(readFileSync(resolve(root, 'conference-paper.pdf')).length).toBeGreaterThan(10_000);
    expect(readFileSync(resolve(root, 'architecture.png')).length).toBeGreaterThan(1000);
    expect(readFileSync(resolve(root, 'vehmf.png')).length).toBeGreaterThan(1000);
  });
});
