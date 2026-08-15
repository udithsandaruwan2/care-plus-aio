/** Public ops contact (Step 75). Override with VITE_SUPPORT_EMAIL at build time. */
export const SUPPORT_EMAIL =
  (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined)?.trim() || 'support@careplus.lk';
