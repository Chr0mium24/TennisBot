import { describe, expect, test } from 'bun:test';
import { predictTrajectory } from './index.js';

describe('prediction placeholders', () => {
  test('keeps trajectory prediction explicitly unimplemented', () => {
    expect(predictTrajectory([], { generatedAtUnixMs: 1710000000000 })).toEqual({
      status: 'not-implemented',
      reason: 'Trajectory and landing prediction will be migrated from BallTrajectoryLab into packages/core.',
    });
  });
});
