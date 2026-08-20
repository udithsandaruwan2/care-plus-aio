/** Register the Workbox-powered service worker (Step 93). No-op outside production builds. */
export async function registerCarePlusSW(): Promise<void> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return;
  }
  if (!import.meta.env.PROD) {
    return;
  }
  const { registerSW } = await import('virtual:pwa-register');
  registerSW({ immediate: true });
}
