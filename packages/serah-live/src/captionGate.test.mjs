import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { acceptCaption } from '../.test-out/captionGate.js';

describe('acceptCaption', () => {
  it('drops an inhale and keeps a real request', () => {
    assert.equal(acceptCaption('uhh'), false);
    assert.equal(acceptCaption('h'), false);
    assert.equal(acceptCaption('the', 0.2), false);
    assert.equal(acceptCaption('I need a nurse today', 0.9), true);
    assert.equal(acceptCaption('please find a caregiver near me', 0.3), true);
  });
});
