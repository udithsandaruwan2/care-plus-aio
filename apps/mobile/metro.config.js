const { getDefaultConfig } = require('expo/metro-config');
const path = require('node:path');

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, '../..');

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const root = escapeRegExp(monorepoRoot);

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(projectRoot);

// Expo SDK 54 auto-configures monorepo watch/resolve. Only block noisy/unreadable trees.
config.resolver.blockList = [
  new RegExp(`${root}/backend/.*`),
  new RegExp(`${root}/ml/.*`),
  new RegExp(`${root}/infra/.*`),
  new RegExp(`${root}/apps/web/.*`),
  new RegExp(`${root}/\\.git/.*`),
];

module.exports = config;
