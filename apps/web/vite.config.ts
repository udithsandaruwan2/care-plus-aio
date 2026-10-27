/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import fs from 'node:fs';
import path from 'node:path';

const STALE_SW_KILL_SWITCH = `/* Retire stale app-shell service workers. */
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (event) {
  event.waitUntil((async function () {
    var keys = await caches.keys();
    await Promise.all(keys.map(function (k) { return caches.delete(k); }));
    await self.registration.unregister();
    var clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    await Promise.all(clients.map(function (c) { return c.navigate ? c.navigate(c.url) : undefined; }));
  })());
});
`;

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      injectRegister: false,
      includeAssets: ['offline.html', 'icons/*.png'],
      manifest: {
        name: 'Care Plus',
        short_name: 'Care Plus',
        description: 'Multilingual voice-driven caregiver matching',
        theme_color: '#0b3d4a',
        background_color: '#061820',
        display: 'standalone',
        orientation: 'portrait-primary',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2,webp}'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
      devOptions: {
        enabled: false,
        type: 'module',
      },
    }),
    {
      name: 'careplus-sw-alias',
      apply: 'build',
      enforce: 'post',
      closeBundle: {
        sequential: true,
        order: 'post',
        handler() {
          const dist = path.resolve(__dirname, 'dist');
          const sw = path.join(dist, 'sw.js');
          if (!fs.existsSync(sw)) return;
          fs.copyFileSync(sw, path.join(dist, 'cp-sw.js'));
          fs.writeFileSync(sw, STALE_SW_KILL_SWITCH, 'utf8');
        },
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  optimizeDeps: {
    // Workspace packages are source TS — prebundling them freezes stale exports
    // and whitescreens the app after core/api-client changes.
    exclude: ['@care-plus/core', '@care-plus/api-client', '@care-plus/ui-tokens', '@care-plus/serah-live'],
  },
  build: {
    modulePreload: {
      // Do not prefetch map/charts/3D on the first paint — they load with their routes.
      resolveDependencies(filename, deps) {
        return deps.filter(
          (dep) => !/\/(leaflet|three|recharts)-/.test(dep) && !dep.includes('leaflet-'),
        );
      },
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/recharts')) return 'recharts';
          if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet')) {
            return 'leaflet';
          }
          if (id.includes('node_modules/three') || id.includes('node_modules/@react-three')) {
            return 'three';
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    fs: {
      allow: [path.resolve(__dirname, '../..')],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
