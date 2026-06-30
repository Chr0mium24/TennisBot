import { describe, expect, test } from 'bun:test';
import type { TriangulatedBallPoint3D } from '../../contracts/src/index.js';
import { predictTrajectory } from './index.js';

describe('projectile trajectory prediction', () => {
  test('falls back to two-frame samples and landing point with z as vertical-up', () => {
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
      expect(result.curve.model).toBe('projectile-3d-two-frame-constant-gravity');
      expect(result.curve.samples).toHaveLength(5);
      expect(result.curve.samples[0]?.positionMeters).toEqual({ x: 2, y: 1, z: 4 });
      expect(result.landingPoint?.tOffsetSec).toBeCloseTo(1.259, 3);
      expect(result.landingPoint?.positionMeters.x).toBeCloseTo(4.518, 3);
      expect(result.landingPoint?.positionMeters.y).toBeCloseTo(2.259, 3);
      expect(result.landingPoint?.positionMeters.z).toBe(0);
    }
  });

  test('uses weighted fixed-gravity LS by default once enough points are available', () => {
    const points = sampleTrajectory({
      count: 5,
      intervalMs: 50,
      startUnixMs: 1710000000000,
      start: { x: 0.1, y: 0.4, z: 1.2 },
      velocity: { x: 1.5, y: 4, z: 3.2 },
    });
    const result = predictTrajectory(points, {
      generatedAtUnixMs: 1710000000500,
      sampleCount: 4,
      landingSurfaceZMeters: 0,
    });

    expect(result.status).toBe('ok');
    if (result.status === 'ok') {
      const expectedCurrent = points.at(-1)?.positionMeters;
      expect(result.curve.model).toBe('projectile-3d-weighted-ls9-constant-gravity');
      expect(result.curve.sourcePointIds).toEqual(points.map((item) => item.pointId));
      expect(result.curve.samples[0]?.positionMeters.x).toBeCloseTo(expectedCurrent?.x ?? 0, 8);
      expect(result.curve.samples[0]?.positionMeters.y).toBeCloseTo(expectedCurrent?.y ?? 0, 8);
      expect(result.curve.samples[0]?.positionMeters.z).toBeCloseTo(expectedCurrent?.z ?? 0, 8);
      expect(result.landingPoint?.positionMeters.z).toBe(0);
    }
  });

  test('uses RANSAC guard to reject a jumped triangulation point by default', () => {
    const clean = sampleTrajectory({
      count: 10,
      intervalMs: 50,
      startUnixMs: 1710000000000,
      start: { x: -0.2, y: 0.3, z: 1.1 },
      velocity: { x: 1.1, y: 5.2, z: 3.6 },
    });
    const withOutlier = clean.map((item, index) =>
      index === 8
        ? point('p8-outlier', item.timestampUnixMs, {
            x: item.positionMeters.x + 2.5,
            y: item.positionMeters.y - 3.0,
            z: item.positionMeters.z + 1.8,
          })
        : item,
    );

    const robust = predictTrajectory(withOutlier, {
      generatedAtUnixMs: 1710000000600,
      sampleCount: 5,
      landingSurfaceZMeters: 0,
    });
    const cleanReference = predictTrajectory(clean, {
      generatedAtUnixMs: 1710000000600,
      method: 'weighted-ls',
      sampleCount: 5,
      landingSurfaceZMeters: 0,
    });
    const pollutedWeighted = predictTrajectory(withOutlier, {
      generatedAtUnixMs: 1710000000600,
      method: 'weighted-ls',
      sampleCount: 5,
      landingSurfaceZMeters: 0,
    });

    expect(robust.status).toBe('ok');
    expect(cleanReference.status).toBe('ok');
    expect(pollutedWeighted.status).toBe('ok');
    if (robust.status === 'ok' && cleanReference.status === 'ok' && pollutedWeighted.status === 'ok') {
      expect(robust.curve.model).toBe('projectile-3d-weighted-ls9-ransac-constant-gravity');
      expect(robust.curve.sourcePointIds).not.toContain('p8-outlier');
      expect(robust.landingPoint?.positionMeters.x).toBeCloseTo(cleanReference.landingPoint?.positionMeters.x ?? 0, 4);
      expect(robust.landingPoint?.positionMeters.y).toBeCloseTo(cleanReference.landingPoint?.positionMeters.y ?? 0, 4);
      expect(Math.abs((pollutedWeighted.landingPoint?.positionMeters.x ?? 0) - (cleanReference.landingPoint?.positionMeters.x ?? 0)))
        .toBeGreaterThan(0.2);
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

function sampleTrajectory(options: {
  count: number;
  intervalMs: number;
  startUnixMs: number;
  start: { x: number; y: number; z: number };
  velocity: { x: number; y: number; z: number };
}): TriangulatedBallPoint3D[] {
  return Array.from({ length: options.count }, (_, index) => {
    const tSec = (options.intervalMs * index) / 1000;
    return point(`p${index}`, options.startUnixMs + options.intervalMs * index, {
      x: options.start.x + options.velocity.x * tSec,
      y: options.start.y + options.velocity.y * tSec,
      z: options.start.z + options.velocity.z * tSec - 0.5 * 9.81 * tSec * tSec,
    });
  });
}
