import { describe, expect, it } from 'vitest';
import { AssistantState } from '@care-plus/core';
import {
  AMP_EPS,
  AMP_PUBLISH_HZ,
  IDLE_FRAME_SEC,
  LIVE_FRAME_SEC,
  frameIntervalSec,
  isHotNeuralState,
  neuronMatricesDirty,
  shouldPublishAmplitude,
} from './frameBudget';

describe('frameBudget', () => {
  it('runs idle states at 30 fps and speech/emergency at 60 fps', () => {
    expect(frameIntervalSec(AssistantState.IDLE)).toBe(IDLE_FRAME_SEC);
    expect(frameIntervalSec(AssistantState.LISTENING)).toBe(IDLE_FRAME_SEC);
    expect(frameIntervalSec(AssistantState.THINKING)).toBe(IDLE_FRAME_SEC);
    expect(isHotNeuralState(AssistantState.SPEAKING)).toBe(true);
    expect(isHotNeuralState(AssistantState.EMERGENCY)).toBe(true);
    expect(frameIntervalSec(AssistantState.SPEAKING)).toBe(LIVE_FRAME_SEC);
    expect(frameIntervalSec(AssistantState.EMERGENCY)).toBe(LIVE_FRAME_SEC);
  });

  it('skips the 104-neuron rewrite when amplitude and state are stable', () => {
    expect(neuronMatricesDirty({ hot: false, ampDelta: AMP_EPS / 2, stateChanged: false })).toBe(
      false,
    );
    expect(neuronMatricesDirty({ hot: false, ampDelta: AMP_EPS, stateChanged: false })).toBe(true);
    expect(neuronMatricesDirty({ hot: false, ampDelta: 0, stateChanged: true })).toBe(true);
    expect(neuronMatricesDirty({ hot: true, ampDelta: 0, stateChanged: false })).toBe(true);
  });

  it('throttles amplitude React publishes to about 15 Hz', () => {
    expect(shouldPublishAmplitude(0, 0)).toBe(false);
    expect(shouldPublishAmplitude(1000 / AMP_PUBLISH_HZ, 0)).toBe(true);
    expect(shouldPublishAmplitude(1000 / AMP_PUBLISH_HZ - 1, 0)).toBe(false);
  });
});
