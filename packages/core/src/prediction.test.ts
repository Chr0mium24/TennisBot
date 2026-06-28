import { describe, expect, test } from 'bun:test';
import type { TriangulatedBallPoint3D } from '../../contracts/src/index.js';
import { predictTrajectory } from './index.js';

describe('projectile trajectory prediction', () => {
  test('predicts samples and landing point with z as vertical-up', () => {
    const result = predictTrajectory(
      [
        point('p0', 1710000000000, { x: 0, y: 0, z: 1 }),
        point('p1', 1710000001000, { x: 2, y: 1, z: 4 }),
      ],
      {
        generatedAtUnixMs: 1710000001100,
        gravityMetersPerSecondSquared: 9.81,
        horizonSec: 0.5,
        sampleCount: 5,
        landingSurfaceZMeters: 0,
      },
    );

    expect(result.status).toBe('ok');
    if (result.status === 'ok') {
      expect(result.curve.model).toBe('projectile-3d-constant-gravity');
      expect(result.curve.samples).toHaveLength(5);
      expect(result.curve.samples[0]?.positionMeters).toEqual({ x: 2, y: 1, z: 4 });
      expect(result.landingPoint?.tOffsetSec).toBeCloseTo(1.259, 3);
      expect(result.landingPoint?.positionMeters.x).toBeCloseTo(4.518, 3);
      expect(result.landingPoint?.positionMeters.y).toBeCloseTo(2.259, 3);
      expect(result.landingPoint?.positionMeters.z).toBe(0);
    }
  });

  test('returns a no-landing prediction when the configured surface is unreachable', () => {
    const result = predictTrajectory(
      [
        point('p0', 1710000000000, { x: 0, y: 0, z: 1 }),
        point('p1', 1710000001000, { x: 1, y: 1, z: 1 }),
      ],
      {
        generatedAtUnixMs: 1710000001100,
        horizonSec: 0.25,
        sampleCount: 3,
        landingSurfaceZMeters: 10,
      },
    );

    expect(result.status).toBe('ok');
    if (result.status === 'ok') {
      expect(result.landingPoint).toBeNull();
      expect(result.curve.samples.at(-1)?.tOffsetSec).toBe(0.25);
    }
  });

  test('rejects insufficient or invalid input', () => {
    expect(predictTrajectory([point('only', 1710000000000, { x: 0, y: 0, z: 1 })], { generatedAtUnixMs: 1 }))
      .toEqual({ status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' });

    expect(
      predictTrajectory(
        [
          point('p0', 1710000000000, { x: 0, y: 0, z: 1 }),
          point('p1', 1710000000000, { x: 1, y: 1, z: 1 }),
        ],
        { generatedAtUnixMs: 1 },
      ),
    ).toEqual({ status: 'invalid-input', reason: 'Trajectory prediction requires increasing point timestamps.' });
  });
});

function point(pointId: string, timestampUnixMs: number, positionMeters: { x: number; y: number; z: number }): TriangulatedBallPoint3D {
  return {
    pointId,
    timestampUnixMs,
    positionMeters,
    sourcePairId: `${pointId}:pair`,
    reprojectionErrorPx: 0.5,
  };
}
