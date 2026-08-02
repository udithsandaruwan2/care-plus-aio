const { getDefaultConfig } = require('expo/metro-config');
const path = require('node:path');
const exclusionList = require('metro-config/src/defaults/exclusionList');

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, '../..');

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const root = escapeRegExp(monorepoRoot);

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(projectRoot);

// Only watch shared packages — not backend/ml (permission + crawl noise).
config.watchFolders = [
  path.resolve(monorepoRoot, 'packages/core'),
  path.resolve(monorepoRoot, 'packages/api-client'),
  path.resolve(monorepoRoot, 'packages/ui-tokens'),
  path.resolve(monorepoRoot, 'node_modules'),
];

config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(monorepoRoot, 'node_modules'),
];
config.resolver.disableHierarchicalLookup = true;

config.resolver.blockList = exclusionList([
  new RegExp(`${root}/backend/.*`),
  new RegExp(`${root}/ml/.*`),
  new RegExp(`${root}/infra/.*`),
  new RegExp(`${root}/apps/web/.*`),
  new RegExp(`${root}/\\.git/.*`),
]);

module.exports = config;
