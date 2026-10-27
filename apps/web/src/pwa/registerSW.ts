/** Register the Workbox-powered service worker (Step 93). No-op outside production builds. */
export async function registerCarePlusSW(): Promise<void> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return;
  }
  if (!import.meta.env.PROD) {
    return;
  }
  const stale = await navigator.serviceWorker.getRegistrations();
  await Promise.all(
    stale
      .filter((reg) => !reg.active?.scriptURL.includes('/cp-sw.js'))
      .map((reg) => reg.unregister()),
  );
  await navigator.serviceWorker.register('/cp-sw.js', {
    scope: '/',
    updateViaCache: 'none',
  });
}
