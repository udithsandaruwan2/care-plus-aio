import { describe, expect, it } from 'vitest';
import { itemsForRole, mobileTabsForRole } from './hubNav';

describe('hubNav', () => {
  it('keeps five Pixel-width tabs for a patient', () => {
    const tabs = mobileTabsForRole('patient');
    expect(tabs).toHaveLength(5);
    expect(tabs.map((t) => t.path)).toEqual(['/hub', '/app', '/requests', '/messages', '/account']);
  });

  it('opens Serah from the patient sidebar list', () => {
    expect(itemsForRole('patient').some((item) => item.path === '/app')).toBe(true);
  });
});
