import { describe, expect, it } from 'vitest';
import { inferPostMatchAction } from './postMatchVoiceCommand';
import { composeRequestMessage } from './composeRequestMessage';

describe('inferPostMatchAction', () => {
  it('opens a profile from spoken view/show phrases', () => {
    expect(inferPostMatchAction('view profile')?.type).toBe('view_profile');
    expect(inferPostMatchAction('show me the profile')?.type).toBe('view_profile');
  });

  it('opens schedule from spoken schedule phrases', () => {
    expect(inferPostMatchAction('show the schedule')?.type).toBe('book_shift');
    expect(inferPostMatchAction('book a visit')?.type).toBe('book_shift');
  });

  it('starts a request from send-the-request language', () => {
    expect(inferPostMatchAction('send the request')?.type).toBe('request');
    expect(inferPostMatchAction('book the caregiver')?.type).toBe('request');
    expect(inferPostMatchAction('booking')?.type).toBe('request');
    expect(inferPostMatchAction('book them')?.type).toBe('request');
  });
});

describe('composeRequestMessage', () => {
  it('includes caregiver name and condition', () => {
    const note = composeRequestMessage({
      caregiverName: 'Lakmali Herath',
      intent: { condition: 'diabetes', care_level: 'intermediate', language: 'Sinhala' },
    });
    expect(note).toContain('Lakmali Herath');
    expect(note).toContain('diabetes');
    expect(note).toContain('Sinhala');
  });
});
