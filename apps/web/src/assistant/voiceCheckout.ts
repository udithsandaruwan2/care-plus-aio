import { ApiError, userNeedsOtp, type CarePackage, type CatalogAddOn, type SerahAction } from '@care-plus/api-client';
import { api } from '../auth/api';
import { loadCachedUser } from '../auth/session';
import { appNavigate } from './appNavigate';
import {
  parseDaysFromText,
  resolveAddOns,
  resolvePackageFromAction,
} from './resolvePackage';
import { useAssistant } from './store';
import { speakSerah, stopSpeaking } from './useTts';

export type CatalogSnapshot = {
  packages: CarePackage[];
  addons: CatalogAddOn[];
};

let catalogCache: CatalogSnapshot | null = null;

export async function loadCatalog(force = false): Promise<CatalogSnapshot> {
  if (catalogCache && !force) return catalogCache;
  const [packages, addons] = await Promise.all([
    api.listCarePackages(),
    api.listCatalogAddOns(),
  ]);
  catalogCache = { packages, addons };
  return catalogCache;
}

/** Clear cache (tests). */
export function resetCatalogCache(): void {
  catalogCache = null;
}

function announce(text: string): void {
  if (!text.trim()) return;
  const store = useAssistant.getState();
  const last = [...store.chat].reverse().find((m) => m.role === 'serah');
  if (last?.text.trim() === text.trim()) return;
  stopSpeaking();
  store.appendChat({ role: 'serah', text, route: 'ACTION' });
  void speakSerah(text, store.uiLanguage);
}

export function packagesListNarration(packages: CarePackage[]): string {
  const top = [...packages]
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id)
    .slice(0, 3);
  if (!top.length) {
    return 'I couldn’t load care packages right now. Open checkout from Care requests when you’re ready.';
  }
  const listed = top
    .map((p, i) => `${i + 1}: ${p.name}`)
    .join('; ');
  return (
    `Here are a few packages: ${listed}. ` +
    `Say a name, a number, how many days, or add-ons like meals — then say continue to payment when it looks right.`
  );
}

export function packageSelectedNarration(
  name: string,
  days: number,
  addonNames: string[],
): string {
  const extras =
    addonNames.length > 0 ? ` with ${addonNames.join(' and ')}` : '';
  return (
    `Got it — ${name} for ${days} day${days === 1 ? '' : 's'}${extras}. ` +
    `Say continue to payment when you’re ready. I’ll open the pay screen, but you still need to tap Pay yourself.`
  );
}

export function payReadyNarration(): string {
  return `I’ve filled the order — tap Pay on this screen to confirm. I won’t charge anything by voice.`;
}

export function otpNeededNarration(): string {
  return (
    `Before checkout, please verify the email OTP on screen. ` +
    `After that, say continue to payment again.`
  );
}

/** Speak the first few catalog packages after accept (bookingStage=packages). */
export async function offerPackagesAfterAccept(): Promise<void> {
  try {
    const { packages } = await loadCatalog();
    announce(packagesListNarration(packages));
  } catch {
    announce(
      `Next we can pick a package. Say Basic, Intermediate, or how many days you need.`,
    );
  }
}

export type SelectPackageResult =
  | { ok: true; packageId: number; days: number; addonIds: number[] }
  | { ok: false; error: string };

/** Apply voice package / days / add-ons onto ``checkoutDraft``. */
export async function selectPackageFromAction(
  action: SerahAction,
): Promise<SelectPackageResult> {
  const store = useAssistant.getState();
  try {
    const { packages, addons } = await loadCatalog();
    const pkg = resolvePackageFromAction(packages, action);
    if (!pkg) {
      const error =
        'I couldn’t tell which package you want. Say Basic Home Care, number one, or Intermediate.';
      announce(error);
      return { ok: false, error };
    }

    const spoken = [action.name_query, action.addon_query].filter(Boolean).join(' ');
    const daysFromAction =
      typeof action.days === 'number' && action.days >= 1 ? action.days : null;
    const days =
      daysFromAction ??
      parseDaysFromText(spoken) ??
      store.checkoutDraft.days ??
      pkg.default_days;

    const fromActionAddons = resolveAddOns(addons, {
      addonIds: action.addon_ids,
      addonQuery: action.addon_query,
      nameQuery: action.name_query,
    });
    // Keep prior add-ons when this turn did not mention any.
    const addonIds =
      fromActionAddons.length > 0
        ? fromActionAddons.map((a) => a.id)
        : action.addon_query || /\b(add|with|include|plus)\b/i.test(spoken)
          ? []
          : store.checkoutDraft.addonIds;

    const addonNames = addons
      .filter((a) => addonIds.includes(a.id))
      .map((a) => a.name);

    store.setCheckoutDraft({
      packageId: pkg.id,
      packageName: pkg.name,
      addonIds,
      days,
      orderId: store.checkoutDraft.orderId,
    });
    store.setBookingStage('packages');
    announce(packageSelectedNarration(pkg.name, days, addonNames));
    return { ok: true, packageId: pkg.id, days, addonIds };
  } catch (err) {
    const error =
      err instanceof Error ? err.message : 'Could not load packages. Try again in a moment.';
    announce(error);
    return { ok: false, error };
  }
}

export type ConfirmCheckoutResult =
  | { ok: true; orderId: number; needsOtp?: false }
  | { ok: true; needsOtp: true }
  | { ok: false; error: string };

/**
 * POST /checkout/ from the voice draft, navigate to OrderPayPage.
 * Never confirms payment — Pay stays a manual button.
 */
export async function confirmCheckoutFromVoice(): Promise<ConfirmCheckoutResult> {
  const store = useAssistant.getState();
  const careRequestId = store.careRequestId;
  const draft = store.checkoutDraft;

  if (careRequestId == null) {
    const error =
      'I don’t have an accepted care request yet. Wait for the caregiver to accept, then we can checkout.';
    announce(error);
    return { ok: false, error };
  }

  if (draft.packageId == null) {
    // Try defaulting to first catalog package so "continue to payment" still works.
    try {
      const { packages } = await loadCatalog();
      const first = [...packages].sort(
        (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id,
      )[0];
      if (first) {
        store.setCheckoutDraft({
          packageId: first.id,
          packageName: first.name,
          days: draft.days || first.default_days,
        });
      }
    } catch {
      /* fall through */
    }
  }

  const next = useAssistant.getState().checkoutDraft;
  if (next.packageId == null) {
    const error = 'Pick a package first — say Basic, Intermediate, or number one.';
    announce(error);
    return { ok: false, error };
  }

  if (userNeedsOtp(loadCachedUser())) {
    announce(otpNeededNarration());
    appNavigate('/otp');
    return { ok: true, needsOtp: true };
  }

  try {
    const order = await api.createCheckout({
      care_request_id: careRequestId,
      package_id: next.packageId,
      addon_ids: next.addonIds,
      days: next.days,
    });
    store.setCheckoutDraft({ orderId: order.id });
    store.setBookingStage('pay');
    announce(payReadyNarration());
    appNavigate(`/orders/${order.id}/pay`);
    return { ok: true, orderId: order.id };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 403 || err.status === 401)) {
      const detail = String(err.message || '').toLowerCase();
      if (detail.includes('otp')) {
        announce(otpNeededNarration());
        appNavigate('/otp');
        return { ok: true, needsOtp: true };
      }
    }
    const error =
      err instanceof Error ? err.message : 'Could not create the checkout order. Try again.';
    announce(error);
    return { ok: false, error };
  }
}
