#!/usr/bin/env node
/**
 * Step 80 — fail CI if the Vite entry JS chunk exceeds the first-load budget.
 *
 * Uncompressed (on-disk) size of the module referenced by dist/index.html.
 * Also requires named vendor chunks for analytics (recharts) and browse (leaflet).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
const htmlPath = path.join(dist, 'index.html');
const ENTRY_BUDGET = 450 * 1024;

if (!fs.existsSync(htmlPath)) {
  console.error('check-entry-budget: dist/index.html missing — run vite build first.');
  process.exit(1);
}

const html = fs.readFileSync(htmlPath, 'utf8');
const scriptMatch = html.match(/<script type="module"[^>]*src="([^"]+)"/);
if (!scriptMatch) {
  console.error('check-entry-budget: no module script in dist/index.html');
  process.exit(1);
}

const entryRel = scriptMatch[1].replace(/^\//, '');
const entryPath = path.join(dist, entryRel);
if (!fs.existsSync(entryPath)) {
  console.error(`check-entry-budget: entry file missing: ${entryPath}`);
  process.exit(1);
}

const entryBytes = fs.statSync(entryPath).size;
const assetsDir = path.join(dist, 'assets');
const assets = fs.existsSync(assetsDir) ? fs.readdirSync(assetsDir) : [];
const hasRecharts = assets.some((name) => name.startsWith('recharts-') && name.endsWith('.js'));
const hasLeaflet = assets.some((name) => name.startsWith('leaflet-') && name.endsWith('.js'));

const lines = [
  `entry ${entryRel} = ${entryBytes} bytes (budget ${ENTRY_BUDGET})`,
  `recharts chunk: ${hasRecharts ? 'yes' : 'NO'}`,
  `leaflet chunk: ${hasLeaflet ? 'yes' : 'NO'}`,
];
console.log(lines.join('\n'));

let failed = false;
if (entryBytes > ENTRY_BUDGET) {
  console.error(`check-entry-budget: entry chunk ${entryBytes} exceeds ${ENTRY_BUDGET}`);
  failed = true;
}
if (!hasRecharts) {
  console.error('check-entry-budget: missing recharts-*.js chunk');
  failed = true;
}
if (!hasLeaflet) {
  console.error('check-entry-budget: missing leaflet-*.js chunk');
  failed = true;
}
if (html.includes('fonts.googleapis.com') || html.includes('fonts.gstatic.com')) {
  console.error('check-entry-budget: Google Fonts CDN still referenced');
  failed = true;
}
if (/modulepreload[^>]+(leaflet|three|recharts)-/.test(html)) {
  console.error('check-entry-budget: map/charts/3D still modulepreloaded on first load');
  failed = true;
}

process.exit(failed ? 1 : 0);
