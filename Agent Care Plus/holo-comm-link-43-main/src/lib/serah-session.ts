import { AI_CONSENT_SCOPE } from "@care-plus/api-client";
import { api, clearTokens, getAccessToken, saveTokens } from "./careplus-api";

const DEMO_EMAIL = "demo.patient@careplus.local";
const DEMO_PASSWORD = "CarePlus!demo";

export type SessionStatus = "booting" | "online" | "degraded" | "error";

export type BootResult = {
  status: SessionStatus;
  userId: number | null;
  message: string;
};

/**
 * Presentation boot: demo patient JWT + AI consent so /voice/turn/ works immediately.
 */
export async function ensureSerahSession(): Promise<BootResult> {
  try {
    let access = getAccessToken();
    if (!access) {
      const tokens = await api.login(DEMO_EMAIL, DEMO_PASSWORD);
      saveTokens(tokens.access, tokens.refresh);
      access = tokens.access;
    }

    const me = await api.me();
    const consent = await api.getConsent();
    const granted = Boolean(consent.current?.[AI_CONSENT_SCOPE]);
    if (!granted) {
      await api.setConsent(AI_CONSENT_SCOPE, true);
    }

    return {
      status: "online",
      userId: me.id,
      message: `Linked as ${me.email}`,
    };
  } catch (err) {
    clearTokens();
    const message = err instanceof Error ? err.message : "Could not connect to Care Plus API";
    return { status: "error", userId: null, message };
  }
}
