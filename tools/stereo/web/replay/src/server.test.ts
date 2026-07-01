import { describe, expect, test } from "bun:test";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { listSessions, loadSession } from "./server";

describe("stereo replay server data access", () => {
  test("lists and loads recorded stereo sessions", async () => {
    const root = await mkdtemp(join(tmpdir(), "stereo-replay-"));
    const session = join(root, "stereo_20260701_120000_CST");
    await mkdir(session, { recursive: true });
    await writeFile(
      join(session, "session.json"),
      JSON.stringify({
        schema_version: "tennisbot.stereo_recording.v1",
        session_id: "stereo_20260701_120000_CST",
        created_at: "2026-07-01T04:00:00.000Z",
      }),
    );
    await writeFile(
      join(session, "points.ndjson"),
      [
        JSON.stringify({
          frame_id: 1,
          elapsed_sec: 0.5,
          timestamp_unix_ms: 1770000000000,
          position_m: { x: 0.1, y: 0.2, z: 2.0 },
          confidence: 0.8,
        }),
        JSON.stringify({
          frame_id: 2,
          elapsed_sec: 0.6,
          timestamp_unix_ms: 1770000000100,
          position_m: { x: 0.2, y: 0.25, z: 2.1 },
          confidence: 0.85,
        }),
      ].join("\n"),
    );

    const sessions = await listSessions(root);
    expect(sessions).toHaveLength(1);
    expect(sessions[0]?.pointCount).toBe(2);
    expect(sessions[0]?.durationSec).toBeCloseTo(0.1, 6);

    const detail = await loadSession(root, "stereo_20260701_120000_CST");
    expect(detail.points[0]?.position).toEqual({ x: 0.1, y: 0.2, z: 2.0 });
    expect(detail.summary.createdAt).toBe("2026-07-01T04:00:00.000Z");
  });

  test("rejects session ids outside the runs root", async () => {
    const root = await mkdtemp(join(tmpdir(), "stereo-replay-"));
    await expect(loadSession(root, "../outside")).rejects.toThrow("invalid session id");
  });
});
