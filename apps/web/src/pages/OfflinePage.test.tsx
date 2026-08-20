import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { OfflinePage } from './OfflinePage';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('OfflinePage', () => {
  it('renders an explicit offline message and retry action', () => {
    render(
      <MemoryRouter>
        <OfflinePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: /you’re offline/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

describe('PWA service worker source', () => {
  it('keeps Web Push handlers alongside Workbox precache', () => {
    const sw = readFileSync(resolve(__dirname, '../sw.ts'), 'utf8');
    expect(sw).toContain('precacheAndRoute');
    expect(sw).toContain("addEventListener('push'");
    expect(sw).toContain("addEventListener('notificationclick'");
    expect(sw).toContain('careplus-fonts');
    expect(sw).toContain('careplus-api');
  });

  it('ships offline.html and install icons in public/', () => {
    const offline = readFileSync(resolve(__dirname, '../../public/offline.html'), 'utf8');
    expect(offline).toMatch(/You’re offline|You're offline/);
    expect(readFileSync(resolve(__dirname, '../../public/icons/icon-192.png')).length).toBeGreaterThan(
      100,
    );
    expect(readFileSync(resolve(__dirname, '../../public/icons/icon-512.png')).length).toBeGreaterThan(
      100,
    );
  });
});
